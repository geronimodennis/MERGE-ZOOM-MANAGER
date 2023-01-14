# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['WindowCaptureConfiguration.py'],
             pathex=[],
             binaries=[ ('windowCaptureHandler.cp39-win_amd64.pyd','.'), ('captureRunnerOnThread.cp39-win_amd64.pyd','.'), ('CaptureProcessor.cp39-win_amd64.pyd','.') ],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='COMBINE ZOOM GALLEREIS_1_6_1_for_nvidia',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
