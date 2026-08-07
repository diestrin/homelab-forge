# CI / deployer — read platform deploy secrets only.
path "secret/data/forge/ci/*" {
  capabilities = ["read"]
}

path "secret/metadata/forge/ci/*" {
  capabilities = ["list", "read"]
}
