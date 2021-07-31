Anbox-halium
===========

Getting started
---------------

To get started with Android/LineageOS/BlissROM, you'll need to get
familiar with [Repo](https://source.android.com/source/using-repo.html) and [Version Control with Git](https://source.android.com/source/version-control.html).



To initialize your local repository using the LineageOS trees, use a command like this:
```
repo init -u git://github.com/LineageOS/android.git -b lineage-17.1
```
or... to initialize your local repository using the BlissROM trees, use a command like this:
```
repo init -u https://github.com/BlissRoms/platform_manifest.git -b q
```

And do an initial sync:
```
repo sync
```

Adding Anbox-halium
-------------------

Clone in anbox vendor:
```
git clone https://github.com/Anbox-halium/anbox-patches vendor/anbox
```
Then we generate the manifest:
```
. build/envsetup.sh
anbox-generate-manifest
```
Then sync again:
```
repo sync
```
Then to apply anbox patches:
```
apply-anbox-patches
```

How to build
---------------

Please see the [LineageOS Wiki](https://wiki.lineageos.org/) for building environment setup.

To build anbox for LineageOS:
```
. build/envsetup.sh
lunch lineage_anbox_arm64-userdebug
make systemimage -j$(nproc --all)
make vendorimage -j$(nproc --all)
```
To build anbox for BlissROM:
```
. build/envsetup.sh
lunch bliss_anbox_arm64-userdebug
make systemimage -j$(nproc --all)
make vendorimage -j$(nproc --all)
```

How to install
---------------
Execute command blew: 
```
wget -O - https://github.com/Anbox-halium/anbox-halium/raw/lineage-17.1/scripts/install.sh | bash
```
Note: Run installer on the user you are willing to install anbox on 

Patching kernel
---------------
Running anbox requires: 
* Veth for networking
* Ashmem
* Specific binder nodes (anbox-binder anbox-hwbinder anbox-vndbinder)
Checkout defconfig kernel patcher [script](https://github.com/Anbox-halium/anbox-halium/blob/lineage-17.1/scripts/check-kernel-config.sh) for patching halium devices kernel.
```
check-kernel-config.sh halium_device_defconfig -w 
```
On mainline devices it is highly recommanded to use needed drivers as module. (binder_linux and ashmem_linux)
