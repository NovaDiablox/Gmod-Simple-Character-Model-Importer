param(
    [string]$Python = "python",
    [string]$Name = "MMDCharacterImporter",
    [switch]$UseUPX,
    [switch]$Console,
    [switch]$OneDir
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ReleaseRoot = Join-Path $Root "release"
$PortableDir = Join-Path $ReleaseRoot "${Name}_portable"
$StandaloneExe = Join-Path $ReleaseRoot "${Name}.exe"
$UpdateReleasePageUrl = "https://github.com/SheepyLord/Gmod-Simple-Character-Model-Importer/releases"
$UpdateLatestReleaseApiUrl = "https://api.github.com/repos/SheepyLord/Gmod-Simple-Character-Model-Importer/releases/latest"
$GeneratedBuildInfoDir = $null

function Resolve-ProjectPath([string]$RelativePath) {
    return Join-Path $Root $RelativePath
}

function Get-PathSizeBytes([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return 0
    }
    $Item = Get-Item -LiteralPath $Path
    if (-not $Item.PSIsContainer) {
        return [int64]$Item.Length
    }
    $Measure = Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
    return [int64]($Measure.Sum)
}

function Add-DataPackage([string]$SourceRelative, [string]$DestRelative, [bool]$Required) {
    $Source = Resolve-ProjectPath $SourceRelative
    if (Test-Path -LiteralPath $Source) {
        $script:DataArgs += @("--add-data", "$Source;$DestRelative")
        $script:DataManifest += [ordered]@{
            source = $SourceRelative
            destination = $DestRelative
            size_mb = [math]::Round((Get-PathSizeBytes $Source) / 1MB, 2)
        }
    }
    else {
        if ($Required) {
            throw "Required package data was not found: $SourceRelative"
        }
        else {
            $script:MissingData += $SourceRelative
            Write-Warning "Optional package data was not found: $SourceRelative"
        }
    }
}

function Add-DataIfExists([string]$SourceRelative, [string]$DestRelative) {
    Add-DataPackage $SourceRelative $DestRelative $false
}

function Add-RequiredData([string]$SourceRelative, [string]$DestRelative) {
    Add-DataPackage $SourceRelative $DestRelative $true
}

function Add-DataFileAbsolute([string]$Source, [string]$DestRelative, [string]$SourceLabel) {
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Required generated package data was not found: $Source"
    }
    $script:DataArgs += @("--add-data", "$Source;$DestRelative")
    $script:DataManifest += [ordered]@{
        source = $SourceLabel
        destination = $DestRelative
        size_mb = [math]::Round((Get-PathSizeBytes $Source) / 1MB, 2)
    }
}

function Assert-RequiredFile([string]$RelativePath) {
    $Path = Resolve-ProjectPath $RelativePath
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required package file was not found: $RelativePath"
    }
}

function Write-BundledDataSizeReport() {
    Write-Host "Bundled data size report:"
    $script:DataManifest |
        Sort-Object -Property size_mb -Descending |
        ForEach-Object {
            Write-Host ("  {0,9:N2} MB  {1} -> {2}" -f [double]$_.size_mb, $_.source, $_.destination)
        }
    [double]$TotalMb = 0.0
    foreach ($Item in $script:DataManifest) {
        $TotalMb += [double]$Item.size_mb
    }
    Write-Host ("  {0,9:N2} MB  TOTAL" -f [double]$TotalMb)
}

function Add-BinaryIfExists([string]$Path, [string]$Dest = ".") {
    if (Test-Path -LiteralPath $Path) {
        $script:ExtraArgs += @("--add-binary", "$Path;$Dest")
    }
}

function Invoke-NativeRelaxed([scriptblock]$Command, [switch]$CaptureOutput) {
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if ($CaptureOutput) {
            $output = & $Command 2>&1
            $script:LastNativeOutput = $output
        }
        else {
            & $Command
        }
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
}

Push-Location $Root
try {
    $BuildTimeUtc = (Get-Date).ToUniversalTime().ToString("o")
    $PyInstallerVersionExitCode = Invoke-NativeRelaxed { & $Python -m PyInstaller --version *> $null }
    if ($PyInstallerVersionExitCode -ne 0) {
        throw "PyInstaller is not installed. Run: $Python -m pip install pyinstaller"
    }

    $PythonPrefix = (& $Python -c "import sys; print(sys.prefix)")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not resolve Python prefix."
    }

    $DataArgs = @()
    $DataManifest = @()
    $MissingData = @()
    $GeneratedBuildInfoDir = Join-Path ([System.IO.Path]::GetTempPath()) ("mci_build_info_" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $GeneratedBuildInfoDir | Out-Null
    $BuildInfoPath = Join-Path $GeneratedBuildInfoDir "build_info.json"
    $BuildInfo = [ordered]@{
        app = $Name
        build_time_utc = $BuildTimeUtc
        release_page_url = $UpdateReleasePageUrl
        latest_release_api_url = $UpdateLatestReleaseApiUrl
        source = "pyinstaller"
    }
    $BuildInfoJson = $BuildInfo | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText(
        $BuildInfoPath,
        $BuildInfoJson + [System.Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false)
    )
    Add-DataFileAbsolute $BuildInfoPath "." "generated build_info.json"
    Assert-RequiredFile "external_tools\vtfcmd\VTFCmd.exe"
    Assert-RequiredFile "external_tools\vtfcmd\DevIL.dll"
    Assert-RequiredFile "external_tools\vtfcmd\HLLib.dll"
    Assert-RequiredFile "external_tools\vtfcmd\VTFLib.dll"
    Assert-RequiredFile "external_tools\vtfcmd\msvcm80.dll"
    Assert-RequiredFile "external_tools\vtfcmd\msvcp80.dll"
    Assert-RequiredFile "external_tools\vtfcmd\msvcr80.dll"
    Assert-RequiredFile "external_tools\vc_runtime\vc90\msvcm90.dll"
    Assert-RequiredFile "external_tools\vc_runtime\vc90\msvcp90.dll"
    Assert-RequiredFile "external_tools\vc_runtime\vc90\msvcr90.dll"
    Add-RequiredData "tools" "tools"
    Add-RequiredData "plugins_software" "plugins_software"
    Add-RequiredData "external_tools" "external_tools"
    Add-DataIfExists "blender-4.5.10-windows-x64.zip" "."
    Add-RequiredData "steps.txt" "."
    Add-RequiredData "Translation Templates Write.txt" "."
    Add-RequiredData "README.md" "."
    Add-RequiredData "reference\ref_motion" "reference\ref_motion"
    Add-RequiredData "reference\proportion_trick_script-main_new\README.md" "reference\proportion_trick_script-main_new"
    Add-RequiredData "reference\proportion_trick_script-main_new\operator_proportion_trick.py" "reference\proportion_trick_script-main_new"
    Add-RequiredData "reference\proportion_trick_script-main_new\Proportion_Trick\README.md" "reference\proportion_trick_script-main_new\Proportion_Trick"
    Add-RequiredData "reference\proportion_trick_script-main_new\Proportion_Trick\proportion_trick_4.5.10.blend" "reference\proportion_trick_script-main_new\Proportion_Trick"
    Add-RequiredData "reference\proportion_trick_script-main_new\Proportion_Trick\scripts\4.5.10" "reference\proportion_trick_script-main_new\Proportion_Trick\scripts\4.5.10"
    Add-RequiredData "reference\li_zhiyan_npc\a_pack" "reference\li_zhiyan_npc\a_pack"
    Add-RequiredData "reference\li_zhiyan_npc\3_Flexes\Blender_p3.py" "reference\li_zhiyan_npc\3_Flexes"
    Add-RequiredData "reference\!enhanced_animation_importer_arc\tools" "reference\!enhanced_animation_importer_arc\tools"
    Add-RequiredData "reference\dynamic_model_importer" "reference\dynamic_model_importer"
    Write-BundledDataSizeReport

    $ExtraArgs = @()
    $LibraryBin = Join-Path $PythonPrefix "Library\bin"
    $PythonDlls = Join-Path $PythonPrefix "DLLs"
    if (Test-Path -LiteralPath $LibraryBin) {
        $ExtraArgs += @("--paths", $LibraryBin)
        foreach ($Dll in @(
            "ffi-8.dll",
            "libffi-8.dll",
            "libssl-3-x64.dll",
            "libcrypto-3-x64.dll",
            "libexpat.dll",
            "liblzma.dll",
            "libbz2.dll",
            "zlib.dll",
            "sqlite3.dll"
        )) {
            Add-BinaryIfExists (Join-Path $LibraryBin $Dll)
        }
    }
    if (Test-Path -LiteralPath $PythonDlls) {
        $ExtraArgs += @("--paths", $PythonDlls)
    }
    Add-BinaryIfExists (Join-Path $PythonPrefix "zlib.dll")
    foreach ($Dll in @("msvcm90.dll", "msvcp90.dll", "msvcr90.dll")) {
        Add-BinaryIfExists (Resolve-ProjectPath "external_tools\vc_runtime\vc90\$Dll")
    }

    $IconPath = Resolve-ProjectPath "tools\assets\mmd_character_importer_icon.ico"
    if (-not (Test-Path -LiteralPath $IconPath)) {
        $IconPath = Resolve-ProjectPath "reference\!enhanced_animation_importer_arc\tools\assets\importer_icon.ico"
    }

    $HiddenImports = @(
        "ctypes",
        "_ctypes",
        "numpy",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFilter",
        "PIL.ImageFont",
        "PIL.ImageOps",
        "requests",
        "OpenGL.GL",
        "OpenGL.GLU",
        "OpenGL.arrays.numpymodule",
        "OpenGL.platform.win32",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtOpenGLWidgets"
    )
    $HiddenImportArgs = @()
    foreach ($ImportName in $HiddenImports) {
        $HiddenImportArgs += @("--hidden-import", $ImportName)
    }

    $ExcludedModules = @(
        "IPython",
        "OpenGL_accelerate",
        "OpenGL.GLE",
        "OpenGL.GLUT",
        "OpenGL.Tk",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "matplotlib",
        "pandas",
        "pytest",
        "scipy",
        "sklearn",
        "setuptools",
        "tkinter",
        "torch",
        "unittest",
        "cv2",
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtDesigner",
        "PySide6.QtHelp",
        "PySide6.QtLocation",
        "PySide6.QtNetworkAuth",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtPrintSupport",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtXml"
    )
    foreach ($Module in $ExcludedModules) {
        $ExtraArgs += @("--exclude-module", $Module)
    }
    if (-not $UseUPX) {
        $ExtraArgs += @("--noupx")
    }

    $DistDir = Join-Path $Root "dist"
    $BuildDir = Join-Path $Root "build"
    $DistAppDir = Join-Path $DistDir $Name
    $DistOneFileExe = Join-Path $DistDir "$Name.exe"
    if (Test-Path -LiteralPath $DistAppDir) {
        Remove-Item -LiteralPath $DistAppDir -Recurse -Force
    }
    if (Test-Path -LiteralPath $DistOneFileExe) {
        Remove-Item -LiteralPath $DistOneFileExe -Force
    }
    if (Test-Path -LiteralPath (Join-Path $BuildDir $Name)) {
        Remove-Item -LiteralPath (Join-Path $BuildDir $Name) -Recurse -Force
    }

    $WindowMode = if ($Console) { "--console" } else { "--windowed" }
    $PyInstallerArgs = @(
        "--noconfirm",
        "--clean",
        $WindowMode,
        "--name", $Name
    )
    if ($OneDir) {
        $PyInstallerArgs += @("--onedir", "--contents-directory", "_internal")
    }
    else {
        $PyInstallerArgs += @("--onefile")
    }
    if (Test-Path -LiteralPath $IconPath) {
        $PyInstallerArgs += @("--icon", $IconPath)
    }
    $PyInstallerArgs += $HiddenImportArgs
    $PyInstallerArgs += $DataArgs
    $PyInstallerArgs += $ExtraArgs
    $PyInstallerArgs += @("tools\mmd_character_importer_gui.py")

    Write-Host "Building $Name with PyInstaller..."
    $PyInstallerBuildExitCode = Invoke-NativeRelaxed { & $Python -m PyInstaller @PyInstallerArgs } -CaptureOutput
    if ($PyInstallerBuildExitCode -ne 0) {
        if ($script:LastNativeOutput) {
            Write-Host ($script:LastNativeOutput -join "`n")
        }
        throw "PyInstaller build failed."
    }
    if ($OneDir) {
        if (-not (Test-Path -LiteralPath (Join-Path $DistAppDir "$Name.exe"))) {
            throw "Build completed but $Name.exe was not written."
        }
    }
    else {
        if (-not (Test-Path -LiteralPath $DistOneFileExe)) {
            throw "Build completed but one-file $Name.exe was not written."
        }
    }

    if (-not (Test-Path -LiteralPath $ReleaseRoot)) {
        New-Item -ItemType Directory -Path $ReleaseRoot | Out-Null
    }
    $ResolvedReleaseRoot = (Resolve-Path $ReleaseRoot).Path
    if ($OneDir) {
        $ResolvedPortableDir = [System.IO.Path]::GetFullPath($PortableDir)
        if (-not $ResolvedPortableDir.StartsWith($ResolvedReleaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to replace unexpected release path: $ResolvedPortableDir"
        }
        if (Test-Path -LiteralPath $PortableDir) {
            Remove-Item -LiteralPath $PortableDir -Recurse -Force
        }
        Copy-Item -LiteralPath $DistAppDir -Destination $PortableDir -Recurse
    }
    else {
        $ResolvedStandaloneExe = [System.IO.Path]::GetFullPath($StandaloneExe)
        if (-not $ResolvedStandaloneExe.StartsWith($ResolvedReleaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to replace unexpected release path: $ResolvedStandaloneExe"
        }
        if (Test-Path -LiteralPath $PortableDir) {
            $ResolvedPortableDir = [System.IO.Path]::GetFullPath($PortableDir)
            if (-not $ResolvedPortableDir.StartsWith($ResolvedReleaseRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Refusing to remove unexpected release path: $ResolvedPortableDir"
            }
            Remove-Item -LiteralPath $PortableDir -Recurse -Force
        }
        if (Test-Path -LiteralPath $StandaloneExe) {
            Remove-Item -LiteralPath $StandaloneExe -Force
        }
        Copy-Item -LiteralPath $DistOneFileExe -Destination $StandaloneExe
    }

    $PackageJson = (& $Python -c "import importlib.metadata as m, json, sys; names=sys.argv[1:]; out={};`nfor name in names:`n    try: out[name]=m.version(name)`n    except Exception: out[name]=None`nprint(json.dumps(out, ensure_ascii=False, indent=2))" pyinstaller PySide6 numpy Pillow requests PyOpenGL)
    $Packages = $PackageJson | ConvertFrom-Json
    $BuildMode = if ($OneDir) { if ($Console) { "onedir_console" } else { "onedir_windowed" } } else { if ($Console) { "onefile_console" } else { "onefile_windowed" } }
    $ReleaseTarget = if ($OneDir) { $PortableDir } else { $StandaloneExe }
    $BundledPrograms = @(
        [ordered]@{
            name = "Blender"
            path = "blender-4.5.10-windows-x64.zip"
            required = $false
            role = "Portable Blender 4.5 setup fallback (optional; app can auto-download or use system Blender)"
        },
        [ordered]@{
            name = "VTFCmd"
            path = "external_tools\vtfcmd\VTFCmd.exe"
            required = $true
            role = "Source VTF texture and spawn-icon conversion"
            companion_files = @("DevIL.dll", "HLLib.dll", "VTFLib.dll", "msvcm80.dll", "msvcp80.dll", "msvcr80.dll")
        }
    )
    $BundledRuntimeDlls = @(
        "external_tools\vtfcmd\msvcm80.dll",
        "external_tools\vtfcmd\msvcp80.dll",
        "external_tools\vtfcmd\msvcr80.dll",
        "external_tools\vc_runtime\vc90\msvcm90.dll",
        "external_tools\vc_runtime\vc90\msvcp90.dll",
        "external_tools\vc_runtime\vc90\msvcr90.dll"
    )
    $Manifest = [ordered]@{
        app = $Name
        build_time_utc = $BuildTimeUtc
        release_page_url = $UpdateReleasePageUrl
        latest_release_api_url = $UpdateLatestReleaseApiUrl
        python_executable = (& $Python -c "import sys; print(sys.executable)")
        python_version = (& $Python -c "import sys; print(sys.version)")
        pyinstaller_mode = $BuildMode
        release_target = $ReleaseTarget
        bundled_data = $DataManifest
        bundled_programs = $BundledPrograms
        bundled_runtime_dlls = $BundledRuntimeDlls
        required_external_programs = @(
            [ordered]@{
                name = "Garry's Mod"
                role = "Provides studiomdl.exe, gmad.exe, and game content for final compile/package"
            }
        )
        missing_optional_data = $MissingData
        python_packages = $Packages
        notes = @(
            "Default builds are single-file executables. No _internal folder is required at runtime.",
            "Bundled tools/plugins/templates are extracted by PyInstaller to a temporary runtime folder when the executable starts.",
            "Blender zip is optional. If not bundled, the app will auto-download or use a system-installed Blender.",
            "VTFCmd is bundled for VTF conversion. A separate VTFEdit/VTFCmd install is not required at runtime.",
            "A local Garry's Mod install is still required because StudioMDL and gmad are distributed with Garry's Mod."
        )
    }
    $ManifestPath = if ($OneDir) { Join-Path $PortableDir "dependency_manifest.json" } else { Join-Path $ReleaseRoot "${Name}_dependency_manifest.json" }
    $Manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8

    $ReadmePath = if ($OneDir) { Join-Path $PortableDir "RUN_ME.txt" } else { Join-Path $ReleaseRoot "${Name}_RUN_ME.txt" }
    @(
        "MMD Character Importer build",
        "",
        "Launch: $ReleaseTarget",
        "",
        $(if ($OneDir) { "Do not move or delete the _internal folder; it contains the Blender scripts, plugins, templates, icons, localization, and reference assets required by the workflow." } else { "This is a one-file build. The Blender scripts, plugins, templates, icons, localization, and reference assets are embedded in the executable and extracted temporarily at runtime." }),
        "Bundled external tools: Blender 4.5 zip and VTFCmd.",
        "Runtime requirement: Garry's Mod must be installed so StudioMDL and gmad are available.",
        "Dependency manifest: $([System.IO.Path]::GetFileName($ManifestPath))"
    ) | Set-Content -LiteralPath $ReadmePath -Encoding UTF8

    $ExePath = if ($OneDir) { Join-Path $PortableDir "$Name.exe" } else { $StandaloneExe }
    $SizeMb = [math]::Round((Get-Item -LiteralPath $ExePath).Length / 1MB, 2)
    if ($OneDir) {
        Write-Host "Built portable onedir release: $PortableDir"
    }
    else {
        Write-Host "Built standalone one-file release: $StandaloneExe"
    }
    Write-Host "Executable: $ExePath ($SizeMb MB)"
    Write-Host "Manifest: $ManifestPath"
}
finally {
    if ($GeneratedBuildInfoDir -and (Test-Path -LiteralPath $GeneratedBuildInfoDir)) {
        $ResolvedGeneratedBuildInfoDir = [System.IO.Path]::GetFullPath($GeneratedBuildInfoDir)
        $ResolvedTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        $TempPrefix = Join-Path $ResolvedTempRoot "mci_build_info_"
        if ($ResolvedGeneratedBuildInfoDir.StartsWith($TempPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $GeneratedBuildInfoDir -Recurse -Force
        }
    }
    Pop-Location
}
