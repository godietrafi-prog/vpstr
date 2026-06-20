param([string]$InputFile = "")

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $InputFile -or -not (Test-Path $InputFile)) {
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title  = "Select video file to rotate (90 CW)"
    $dlg.Filter = "Video files (*.mp4;*.mov;*.webm)|*.mp4;*.mov;*.webm"
    if ($dlg.ShowDialog() -ne 'OK') { exit }
    $InputFile = $dlg.FileName
}

$base   = [System.IO.Path]::GetFileNameWithoutExtension($InputFile)
$outFile = Join-Path $dir "media\$base.mp4"
$tmpFile = Join-Path $dir "media\_tmp_$base.mp4"

Write-Host "Input:  $InputFile"
Write-Host "Output: $outFile"
Write-Host ""

ffmpeg -y -i $InputFile -vf "transpose=1" -c:v libx264 -crf 18 -preset fast -c:a aac -movflags +faststart $tmpFile

if ($LASTEXITCODE -eq 0) {
    Move-Item -Force $tmpFile $outFile
    Write-Host "`nDone: $outFile"
} else {
    Write-Host "`nFFmpeg failed."
    if (Test-Path $tmpFile) { Remove-Item $tmpFile }
}

Read-Host "Press Enter to exit"
