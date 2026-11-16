# Copyright 2026 Aditya Sethi
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
import re
import threading
import time
import dbus
import dbus.service
from tools.interfaces import IMediaPlayers
from gi.repository import GLib

stopping = False

MPRIS_PATH = "/org/mpris/MediaPlayer2"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
INTROSPECTION = """<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/><method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/><property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/><property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/><method name="Previous"/><method name="Pause"/><method name="PlayPause"/>
    <method name="Stop"/><method name="Play"/>
    <method name="Seek"><arg name="Offset" type="x" direction="in"/></method>
    <method name="SetPosition"><arg name="TrackId" type="o" direction="in"/><arg name="Position" type="x" direction="in"/></method>
    <method name="OpenUri"><arg name="Uri" type="s" direction="in"/></method>
    <signal name="Seeked"><arg name="Position" type="x"/></signal>
    <property name="PlaybackStatus" type="s" access="read"/><property name="Rate" type="d" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/><property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/><property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/><property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/><property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/><property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
    <method name="GetAll"><arg type="s" direction="in"/><arg type="a{sv}" direction="out"/></method>
    <method name="Set"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/></method>
    <signal name="PropertiesChanged"><arg type="s"/><arg type="a{sv}"/><arg type="as"/></signal>
  </interface>
</node>"""

# PlaybackState actions
ACTION_STOP = 1 << 0
ACTION_PAUSE = 1 << 1
ACTION_PLAY = 1 << 2
ACTION_SKIP_TO_PREVIOUS = 1 << 4
ACTION_SKIP_TO_NEXT = 1 << 5
ACTION_SEEK_TO = 1 << 8
ACTION_PLAY_PAUSE = 1 << 9

def name_part(text):
    return re.sub(r"[^A-Za-z0-9_]", "_", text)

def bus_name_part(text):
    parts = [name_part(p) or "_" for p in text.split(".")]
    return ".".join("_" + p if p[0].isdigit() else p for p in parts)

class MprisPlayer(dbus.service.Object):
    def __init__(self, player, name, art_dir, send):
        self.track = 0
        self.art_dir = art_dir
        self.art = None
        self.art_file = None
        self.art_count = 0
        self.send = send
        self.apply(player)
        # Clients tell players apart by the connection that sends their signals
        try:
            self.bus = dbus.SessionBus(private=True)
        except dbus.DBusException:
            self.delete_art()
            raise
        self.bus.set_exit_on_disconnect(False)
        super().__init__(self.bus, MPRIS_PATH)
        try:
            owned = self.bus.request_name(name, dbus.bus.NAME_FLAG_DO_NOT_QUEUE) == dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER
        except (dbus.DBusException, ValueError):
            owned = False
        if not owned:
            self.close()
            raise dbus.DBusException(f"Can't own {name}")

    def close(self):
        # Closing the connection releases the name
        self.remove_from_connection()
        self.bus.close()
        self.delete_art()

    def delete_art(self):
        if self.art_file and os.path.exists(self.art_file):
            os.unlink(self.art_file)

    def position_us(self):
        p = self.player
        rate = p.speed if p.status == IMediaPlayers.Status.PLAYING else 0
        us = self.base_us + (time.monotonic() - self.base_time) * rate * 1e6
        return int(min(us, p.duration_ms * 1000) if p.duration_ms > 0 else us)

    def track_path(self):
        return dbus.ObjectPath(f"/org/waydroid/track/{name_part(self.player.id)}_{self.track}")

    def set_art(self, data):
        old = self.art_file
        self.art_file = None
        if data and self.art_dir:
            self.art_count += 1
            path = os.path.join(self.art_dir, f"{name_part(self.player.id)}-{self.art_count}.jpg")
            try:
                with open(path + ".part", "wb") as f:
                    f.write(data)
                os.rename(path + ".part", path)
                self.art_file = path
            except OSError as e:
                logging.warning(f"Failed to save album art: {e}")
        if old:
            # A client may still be loading the old picture
            GLib.timeout_add_seconds(10, lambda: os.path.exists(old) and os.unlink(old))

    def metadata(self):
        p = self.player
        m = {"mpris:trackid": self.track_path()}
        if p.duration_ms > 0:
            m["mpris:length"] = dbus.Int64(p.duration_ms * 1000)
        if self.art_file:
            m["mpris:artUrl"] = "file://" + self.art_file
        if p.title:
            m["xesam:title"] = p.title
        if p.artist:
            m["xesam:artist"] = dbus.Array([p.artist], signature="s")
        if p.album:
            m["xesam:album"] = p.album
        return dbus.Dictionary(m, signature="sv")

    def root_props(self):
        return {
            "CanQuit": False, "CanRaise": True, "HasTrackList": False,
            "Identity": self.player.app_name or self.player.package_name,
            "DesktopEntry": f"waydroid.{self.player.package_name}",
            "SupportedUriSchemes": dbus.Array([], signature="s"),
            "SupportedMimeTypes": dbus.Array([], signature="s"),
        }

    def rate(self):
        p = self.player
        return p.speed if p.status == IMediaPlayers.Status.PLAYING and p.speed > 0 else 1.0

    def can(self, actions):
        return bool(self.player.actions & actions)

    def player_props(self):
        p = self.player
        status = {IMediaPlayers.Status.PLAYING: "Playing", IMediaPlayers.Status.PAUSED: "Paused"}.get(p.status, "Stopped")
        rate = self.rate()
        return {
            "PlaybackStatus": status, "Metadata": self.metadata(),
            "Rate": rate, "MinimumRate": min(1.0, rate), "MaximumRate": max(1.0, rate), "Volume": 1.0,
            "Position": dbus.Int64(self.position_us()),
            "CanGoNext": self.can(ACTION_SKIP_TO_NEXT),
            "CanGoPrevious": self.can(ACTION_SKIP_TO_PREVIOUS),
            "CanPlay": self.can(ACTION_PLAY | ACTION_PLAY_PAUSE),
            "CanPause": self.can(ACTION_PAUSE | ACTION_PLAY_PAUSE),
            "CanSeek": self.can(ACTION_SEEK_TO),
            "CanControl": True,
        }

    def apply(self, player):
        self.player = player
        self.base_us, self.base_time = player.position_ms * 1000, time.monotonic()
        if player.art != self.art:
            self.art = player.art
            self.set_art(player.art)

    def update(self, player):
        old = self.player_props()
        new_track = any(getattr(player, k) != getattr(self.player, k) for k in ("title", "artist", "album", "duration_ms"))
        if new_track:
            self.track += 1
        expected = self.position_us()
        was_playing = self.player.status == IMediaPlayers.Status.PLAYING
        self.apply(player)
        changed = {k: v for k, v in self.player_props().items() if k != "Position" and old[k] != v}
        if changed:
            self.PropertiesChanged(PLAYER_IFACE, changed, dbus.Array([], signature="s"))
        # Playing positions drift a little between updates; a paused one only moves by a seek
        if not new_track and abs(self.base_us - expected) > (1000000 if was_playing else 50000):
            self.Seeked(dbus.Int64(self.base_us))

    @dbus.service.method(dbus.INTROSPECTABLE_IFACE, out_signature="s")
    def Introspect(self):
        return INTROSPECTION

    @dbus.service.method(PROPS_IFACE, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        try:
            return self.GetAll(interface)[prop]
        except KeyError:
            raise dbus.exceptions.DBusException(f"No property {prop}", name="org.freedesktop.DBus.Error.InvalidArgs")

    @dbus.service.method(PROPS_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface == ROOT_IFACE:
            return self.root_props()
        if interface == PLAYER_IFACE:
            return self.player_props()
        raise dbus.exceptions.DBusException(f"No interface {interface}", name="org.freedesktop.DBus.Error.UnknownInterface")

    @dbus.service.method(PROPS_IFACE, in_signature="ssv")
    def Set(self, interface, prop, value):
        pass # Rate and Volume stay at 1

    @dbus.service.signal(PROPS_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass

    @dbus.service.signal(PLAYER_IFACE, signature="x")
    def Seeked(self, position):
        pass

    @dbus.service.method(ROOT_IFACE)
    def Raise(self):
        self.send(self.player.id, "raise", 0)

    @dbus.service.method(ROOT_IFACE)
    def Quit(self):
        pass

    def command(self, command, actions, position_ms=0):
        if self.can(actions):
            self.send(self.player.id, command, position_ms)

    @dbus.service.method(PLAYER_IFACE)
    def Next(self):
        self.command("next", ACTION_SKIP_TO_NEXT)

    @dbus.service.method(PLAYER_IFACE)
    def Previous(self):
        self.command("previous", ACTION_SKIP_TO_PREVIOUS)

    @dbus.service.method(PLAYER_IFACE)
    def Pause(self):
        self.command("pause", ACTION_PAUSE | ACTION_PLAY_PAUSE)

    @dbus.service.method(PLAYER_IFACE)
    def PlayPause(self):
        if self.player.status == IMediaPlayers.Status.PLAYING:
            self.Pause()
        else:
            self.Play()

    @dbus.service.method(PLAYER_IFACE)
    def Stop(self):
        self.command("stop", ACTION_STOP)

    @dbus.service.method(PLAYER_IFACE)
    def Play(self):
        self.command("play", ACTION_PLAY | ACTION_PLAY_PAUSE)

    @dbus.service.method(PLAYER_IFACE, in_signature="x")
    def Seek(self, offset):
        position = max(0, self.position_us() + offset)
        if self.player.duration_ms > 0 and position > self.player.duration_ms * 1000:
            self.Next()
        else:
            self.command("seek", ACTION_SEEK_TO, position // 1000)

    @dbus.service.method(PLAYER_IFACE, in_signature="ox")
    def SetPosition(self, track_id, position):
        length = self.player.duration_ms * 1000
        if track_id == self.track_path() and position >= 0 and (length <= 0 or position <= length):
            self.command("seek", ACTION_SEEK_TO, position // 1000)

    @dbus.service.method(PLAYER_IFACE, in_signature="s")
    def OpenUri(self, uri):
        pass

def start(args):
    listeners = []
    players = {}
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    # Without a private runtime directory, players have no cover
    art_dir = os.path.join(runtime_dir, "waydroid-media") if runtime_dir else None

    def remove_all():
        for player_id in list(players):
            remove(player_id)

    # Android numbers its players again after it restarts, so its old players go with it
    def onListenerDeath(listener):
        listeners.remove(listener)
        remove_all()

    def registerListener(listener):
        remove_all()
        listener.addDeathHandler(onListenerDeath)
        listeners.append(listener)

    def send(player_id, command, position_ms):
        for listener in listeners:
            listener.onCommand(player_id, command, int(position_ms))

    def update(player):
        mpris = players.get(player.id)
        if mpris:
            mpris.update(player)
            return
        name = "org.mpris.MediaPlayer2.waydroid." + bus_name_part(player.package_name)
        if any(p.player.package_name == player.package_name for p in players.values()):
            name += ".instance" + name_part(player.id)
        try:
            players[player.id] = MprisPlayer(player, name, art_dir, send)
        except dbus.DBusException as e:
            logging.warning(f"Failed to publish media player {player.package_name}: {e}")

    def remove(player_id):
        mpris = players.pop(player_id, None)
        if mpris:
            mpris.close()

    def service_thread():
        while not stopping:
            IMediaPlayers.add_service(args, registerListener, update, remove)
        remove_all()
        if art_dir:
            for name in os.listdir(art_dir):
                os.unlink(os.path.join(art_dir, name))

    if art_dir:
        os.makedirs(art_dir, exist_ok=True)
    global stopping
    stopping = False
    args.media_manager = threading.Thread(target=service_thread)
    args.media_manager.start()

def stop(args):
    global stopping
    stopping = True
    try:
        if args.mediaPlayersLoop:
            args.mediaPlayersLoop.quit()
    except AttributeError:
        logging.debug("MediaManager service is not even started")
