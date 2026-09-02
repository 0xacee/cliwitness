# Security policy

Security fixes are released for the latest version. Report vulnerabilities
through GitHub private vulnerability reporting.

CliWitness deliberately avoids shell evaluation and strips the inherited
environment down to an explicit allowlist. It does execute the command and
cases named by a spec, so only run specifications you trust. Do not attach
specs or reports containing real credentials to public issues.
