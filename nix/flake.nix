{
  description = "homelab-forge host flake (localpower): Home Manager + system-manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    # OpenAI Codex CLI (codex-cli) is current only on unstable; 25.05 still has 0.1.x.
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager/release-25.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # Keep system-manager on its tested nixpkgs; following nixos-25.05
    # currently breaks evaluation (userborn / activationScripts.hashes).
    system-manager.url = "github:numtide/system-manager";
  };

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-unstable,
      home-manager,
      system-manager,
      ...
    }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        # Vault CLI is BSL; claude-code is Anthropic's proprietary CLI (both unfree).
        config.allowUnfreePredicate =
          pkg:
          builtins.elem (nixpkgs.lib.getName pkg) [
            "vault"
            "claude-code"
          ];
        overlays = [
          (
            _final: _prev:
            let
              unstablePkgs = import nixpkgs-unstable {
                inherit system;
                config.allowUnfreePredicate = pkg: nixpkgs.lib.getName pkg == "claude-code";
              };
            in
            {
              inherit (unstablePkgs) codex;
              # nixpkgs can lag Anthropic releases; pin the official manifest so
              # Home Manager installs the current release reproducibly.
              claude-code = unstablePkgs.claude-code.override {
                manifest = {
                  version = "2.1.292";
                  platforms.linux-x64 = {
                    binary = "claude.zst";
                    checksum = "28509427a53a5c15bd94d022d39013cc4b867a8e6305497f48162dcf91576326";
                    size = 88133859;
                  };
                };
              };
            }
          )
        ];
      };
    in
    {
      formatter.${system} = pkgs.nixfmt-rfc-style;

      homeConfigurations."diestrin@localpower" = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        modules = [ ./home/diestrin.nix ];
      };

      # Alias for shorter `home-manager switch --flake ./nix#diestrin`
      homeConfigurations.diestrin = self.homeConfigurations."diestrin@localpower";

      systemConfigs.localpower = system-manager.lib.makeSystemConfig {
        modules = [ ./hosts/localpower ];
      };

      checks.${system} = {
        home-diestrin = self.homeConfigurations.diestrin.activationPackage;
        system-localpower = self.systemConfigs.localpower;
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          nixfmt-rfc-style
          git
          jq
        ];
      };
    };
}
