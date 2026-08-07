{
  description = "homelab-forge Phase 1 sample: flake + direnv over Cursor SSH";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

  outputs =
    { nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          hello
          jq
          ripgrep
        ];
        shellHook = ''
          echo "hello-flake: L0 sample shell ready (hello, jq, rg)"
        '';
      };
    };
}
