$env:JAVA_HOME = 'D:\jdk-21.0.8'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"

Set-Location $PSScriptRoot\..
mvn -s .\settings.xml clean package
