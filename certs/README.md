# Extra root certificates for the image build

Any `*.crt` file (PEM) in this folder is trusted by the Chorus image, at build time and at run time.

This is for hosts whose HTTPS traffic is re-signed by antivirus software or a company proxy, where downloads inside the build fail with "certificate verify failed" or "invalid peer certificate: UnknownIssuer". Export that software's root certificate from the host's certificate store into this folder as PEM, then rebuild. For example, on Windows in PowerShell, for Norton's web shield:

```powershell
$c = Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -match 'Norton Web/Mail Shield'
"-----BEGIN CERTIFICATE-----`n" + [Convert]::ToBase64String($c.RawData, 'InsertLineBreaks') + "`n-----END CERTIFICATE-----" | Set-Content -Encoding ascii certs\norton-web-shield.crt
```

The `.crt` files are not committed: they belong to one machine.
