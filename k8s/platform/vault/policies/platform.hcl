# Example platform policy — apply with vault policy write (not auto-loaded from git into Vault).
path "secret/data/forge/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/forge/*" {
  capabilities = ["list", "read", "delete"]
}
