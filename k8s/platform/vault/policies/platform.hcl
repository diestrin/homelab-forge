# Example platform policy — apply with vault policy write (not auto-loaded from git into Vault).
# ESO ClusterSecretStore/vault-backend uses a token with this policy.
path "secret/data/forge/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/forge/*" {
  capabilities = ["list", "read", "delete"]
}

# Family Agile ledger sync (ADR-011). Paths are secret/family-agile/{notion,habitica},
# not under forge/, so they need their own grant.
path "secret/data/family-agile/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/family-agile/*" {
  capabilities = ["list", "read", "delete"]
}
