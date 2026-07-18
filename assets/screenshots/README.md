# Demo media provenance

All PNG and GIF files in this directory are captures of the real PyQt6 application.

The displayed pixel arrays are generated deterministically by `scripts/generate_demo_media.py`. They are synthetic textures, do not originate from a patient or medical device, and contain no protected health information. Temporary DICOM containers are deleted immediately after the capture process.

To regenerate the media on Windows:

```powershell
python scripts/generate_demo_media.py
```

