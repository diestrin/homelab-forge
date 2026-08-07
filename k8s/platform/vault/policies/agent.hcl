# Agent AppRole — short-lived task secrets under forge/agents/*
path "secret/data/forge/agents/*" {
  capabilities = ["read"]
}

path "secret/metadata/forge/agents/*" {
  capabilities = ["list", "read"]
}

path "auth/approle/login" {
  capabilities = ["update"]
}
