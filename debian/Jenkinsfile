@Library('ubports-build-tools') _

buildAndProvideDebianPackage()

// Or if the package consists entirely of arch-independent packages:
// (optional optimization, will confuse BlueOcean's live view at build stage)
// buildAndProvideDebianPackage(/* isArchIndependent */ true)

// Optionally, to skip building on some architectures (amd64 is always built):
// buildAndProvideDebianPackage(false, /* ignoredArchs */ ['arm64'])
