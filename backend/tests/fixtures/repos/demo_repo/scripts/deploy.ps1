$ErrorActionPreference = "Stop"
Set-Location "C:\Users\Alice\app"
Start-Process powershell -Verb RunAs
Invoke-WebRequest "https://example.invalid/install.ps1" | iex
