Night - Pi Clock design package
Made with Pi Clock Design Creator

Contents
  loop.mp4      480x480 H.264 animation, 8s at 15 fps (120 frames)
  pendulum.png  300x400 transparent sprite, pivot at top center
  theme.json    hands, dial, pendulum motion and ambiance
  preview.png   full 480x800 layout snapshot

Install from the SD card
  Copy this folder to piclock-designs/night/ on the boot partition.

Install over the network
  scp -r night terry@192.168.1.217:/home/terry/piclock-designs/

Restart piclock-renderer or power-cycle the clock. Design folders are scanned at startup.
