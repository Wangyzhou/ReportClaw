$env:JAVA_HOME = 'D:\jdk-21.0.8'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"

if (-not $env:OPENCLAW_GATEWAY_URL) {
    $env:OPENCLAW_GATEWAY_URL = 'ws://192.168.4.188:18789'
}

Set-Location $PSScriptRoot\..
mvn -s .\settings.xml spring-boot:run
