Notebox - Drag n drop diagram designer

README

Version:
0.0.1

Features
- Drag note over others to select their parent
- Align selected parent's children using buttons: Row, Column, Free
- Auto-save: when toggled, saves every 5 minute in designated file
- Export: images to various file formats (jpeg, png, bmp, svg)
- Zoom: scroll wheel zoom, pan, and dedicated 'resize to fit' button


Bugs
- Repositioning: Press refresh to recalculate positioning of nested items
- Overlap & Overflow: Parents within parents overlap arranged in columns
        Fix by refreshing (Ctrl + R)
        Alternatively you can select the parent and
        switch between rows & columns to rearrange it, 
- Tabs: save before switching files, unsaved changes will disappear without warning
- Disapearing Notes: Not sure why, notes will stop being draggable and vanish
- Crashes: when right-clicking too often

Keyboard Shortcuts

- Duplicate: CTRL + D
- Save: CTRL + S
- Save As: CTRL + SHIFT + S
- Open: CTRL + O
- Refresh: CTRL + R
