$dest = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)

if (-not $dest) {
    $dest = "C:\Users\supor\OneDrive\Área de Trabalho"
}

$WshShell = New-Object -ComObject WScript.Shell

# Atalho 1: Rodar via Python
$S1 = $WshShell.CreateShortcut("$dest\Conciliador - Python.lnk")
$S1.TargetPath = "c:\Users\supor\OneDrive\Imagens\Nova pasta\rodar.bat"
$S1.WorkingDirectory = "c:\Users\supor\OneDrive\Imagens\Nova pasta"
$S1.Save()

# Atalho 2: Rodar via Executavel
$S2 = $WshShell.CreateShortcut("$dest\Conciliador - Executavel.lnk")
$S2.TargetPath = "c:\Users\supor\OneDrive\Imagens\Nova pasta\rodar_exe.bat"
$S2.WorkingDirectory = "c:\Users\supor\OneDrive\Imagens\Nova pasta"
$S2.Save()

Write-Host "Atalhos criados com sucesso na Area de Trabalho: $dest"
