{
  description = "homelab-forge host flake (localpower): Home Manager + system-manager";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
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
