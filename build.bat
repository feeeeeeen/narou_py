@echo off
echo === Narou Downloader ビルド ===

REM テスト実行
echo テスト実行中...
py -3.14 -m pytest tests/ -v
if errorlevel 1 (
    echo テスト失敗。ビルドを中止します。
    pause
    exit /b 1
)

REM PyInstaller実行
echo.
echo PyInstallerでビルド中...
py -3.14 -m PyInstaller narou_py.spec --noconfirm
if errorlevel 1 (
    echo ビルド失敗。
    pause
    exit /b 1
)

echo.
echo ビルド完了: dist\NarouDownloader.exe
pause
