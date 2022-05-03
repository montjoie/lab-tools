* Collection of lab tools

** hsdk.py (to be renamed)

The HSDK board (and the SiFive also) could at first powerup to fail to bring a serial console.
This tool replace ser2net for this board and in case of no serial activity, restart a power cycle.

** cambrionix.py

Control a Cambrionix PDU

** redboot-proxy.py

This tool permit to handle redboot bootloader on LAVA.

This is used on the following boards
- SSI 1328
- intel-ixp42x-welltech-epbx100
- NS 2502

** pyser2net.py

Some board does not work with ser2net due to their embedded tty disapear when board resets.

This is used on the following boards:
- armada-388-clearfog-pro
- am437x-idk-evm

