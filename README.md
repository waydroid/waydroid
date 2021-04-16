Anbox-halium
===========

Getting started
---------------

To get started with Android/LineageOS, you'll need to get
familiar with [Repo](https://source.android.com/source/using-repo.html) and [Version Control with Git](https://source.android.com/source/version-control.html).

To initialize your local repository using the LineageOS trees, use a command like this:
```
repo init -u git://github.com/LineageOS/android.git -b lineage-17.1
```
Add anbox manifest:
```
wget https://raw.githubusercontent.com/Anbox-halium/anbox-halium/lineage-17.1/anbox.xml -P .repo/local_manifests/
```
Then to sync up:
```
repo sync
```
Then to apply sana patches:
```
anbox-patches/apply-patches.sh --mb
```

How to build
---------------
Please see the [LineageOS Wiki](https://wiki.lineageos.org/) for building environment setup.

To build anbox:
```
. build/envsetup.sh
lunch lineage_anbox_arm64-userdebug
make systemimage -j$(nproc --all)
make vendorimage -j$(nproc --all)
```
