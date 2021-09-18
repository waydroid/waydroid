# cloud.drone.io doesn't support templates, so you must copy
# the build snippet contents after the variables definitions.
# You can find an up-to-date snippet here:
# https://github.com/droidian-releng/build-snippets/blob/master/drone/debian-package.star

# Architectures to build. The first one will always be used for 'full'
# builds, i.e. arch-dep, arch-indep and source.
# Following architectures buildds will be used only for arch-dep builds.
BUILD_ON = [
	"amd64",
]

# Extra Debian repositories to add. These can be used to pull packages
# from other feature branches.
# Note that builds with EXTRA_REPOS won't start on production or staging.
EXTRA_REPOS = []

# Host architecture. This can be used to instruct the buildd to
# assume the packages are built (host -> should be executed on) for the
# specified architecture. This is useful for cross-builds.
# You will probably want to leave this value as None (the default) unless
# you know what you're doing.
#
# Note that when HOST_ARCH is not None, builds will be created only
# for the first architecture specified in BUILD_ON.
#
# For example, taking in account the following:
#     BUILD_ON = ["amd64"]
#     HOST_ARCH = "arm64"
# The buildd infrastructure will build on amd64 targetting arm64.
HOST_ARCH = None

########################################################################
# SNIPPET GOES HERE                                                    #
########################################################################

# Snippet for Debian package building
# Copyright (C) 2020 Eugenio "g7" Paolantonio <me@medesimo.eu>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the <organization> nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

SUPPORTED_ARCHITECTURES = [
	"amd64",
	"arm64",
	"armhf",
]

SUPPORTED_SUITES = [
	"bullseye",
	"bookworm",
	"trixie",
]

DRONE_ARCH_MAPPING = {
	"amd64" : "amd64",
	"i386"  : "amd64",
	"arm64" : "arm64",
	"armhf" : "arm",
}

DOCKER_IMAGE = "droidian/build-essential"

TAG_PREFIX = "droidian/"

FEATURE_BRANCH_PREFIX = "feature/"

def return_platform_block_for_architecture(architecture):
	"""
	Returns a platform block for a given architecture.

	:param: architecture: the architecture to use
	"""

	return {
		"platform" : {
			"os" : "linux",
			"arch" : DRONE_ARCH_MAPPING[architecture]
		}
	}

def build_environment_from_secrets(var_list):
	"""
	Returns a suitable environment block for the given list.

	:param: var_list: the list to use
	"""

	return {
		x : {"from_secret" : x}
		for x in var_list
	}

def debian_package_build(suite, architecture, full_build=True, extra_repos=[], host_arch=None):
	"""
	Returns a build pipeline for a Debian package build.

	:param: image: the Docker image to use
	:param: full_build: if True (default), sets RELENG_FULL_BUILD in order
	to trigger a full build (source, arch-indep, arch-dep) rather than
	only an arch-dep build.
	:param: extra_repos: a list containing the extra_repos to add (defaults
	to [])
	:param: host_arch: the host arch to use (defaults to None)
	"""

	result = {
		"kind" : "pipeline",
		"name" : "%s-%s-%s" % (suite, architecture, "full" if full_build else "dep"),
		"type" : "docker",
		"volumes" : [
			{
				"name" : "buildd-results",
				"temp" : {},
			},
		],
		"steps" : [
			{
				"name" : "build",
				"pull" : "always",
				"image" : "quay.io/%s:%s-%s" % (DOCKER_IMAGE, suite, architecture),
				"volumes" : [
					{
						"name" : "buildd-results",
						"path" : "/buildd"
					},
				],
				"commands" : [
					"releng-build-package",
					"find /drone -type f -maxdepth 1 -exec mv {} /buildd \\\;",
				],
				"environment" : {
					"RELENG_FULL_BUILD" : "yes" if full_build else "no",
					"EXTRA_REPOS" : "|".join(extra_repos),
					"RELENG_HOST_ARCH" : host_arch or architecture,
				}
			},
			{
				"name" : "deploy",
				"pull" : "always",
				"image" : "quay.io/%s:%s-%s" % (DOCKER_IMAGE, suite, architecture),
				"volumes" : [
					{
						"name" : "buildd-results",
						"path" : "/buildd"
					},
				],
				"commands" : [
					"ln -s /buildd /tmp/buildd-results",
					"cd /tmp/buildd-results",
					"repo-droidian-sign.sh",
					"repo-droidian-deploy.sh",
				],
				"environment" : build_environment_from_secrets(
					[
						"GPG_STAGINGPRODUCTION_SIGNING_KEY",
						"GPG_STAGINGPRODUCTION_SIGNING_KEYID",
						"INTAKE_SSH_USER",
						"INTAKE_SSH_KEY",
					]
				),
			},
		]
	}

	result.update(return_platform_block_for_architecture(architecture))

	return result

def get_debian_package_pipelines(context, build_on=["amd64"], extra_repos=[], host_arch=None):
	"""
	Returns a list of suitable pipelines for the current build.

	:param: context: a drone context.
	:param: build_on: a list containing the architectures to build for
	(defaults to ["amd64"],
	:param: extra_repos: a list containing the extra_repos to add (defaults
	to [])
	:param: host_arch: the host arch to use (defaults to None)
	"""

	# Determine suite
	suite = None
	if context.build.event == "tag" and context.build.ref.startswith("refs/tags/%s" % TAG_PREFIX):
		# Tag
		_tag = context.build.ref.replace("refs/tags/%s" % TAG_PREFIX, "")
		if _tag.count("/", 2):
			_suite = _tag.split("/")[0]
			if context.build.branch == _suite:
				suite = _suite
	elif context.build.event == "push" and context.build.branch.startswith(FEATURE_BRANCH_PREFIX):
		# Feature branch
		suite = context.build.branch.replace(FEATURE_BRANCH_PREFIX, "").split("/")[0]
	elif context.build.event == "push":
		# Production? (we're going to check later)
		suite = context.build.branch

	if not suite in SUPPORTED_SUITES:
		# Uh oh
		return []

	if not build_on:
		return []

	first_arch = build_on[0]

	if host_arch != None:
		# Force only one buildd
		if host_arch in SUPPORTED_ARCHITECTURES:
			build_on = [first_arch]
		else:
			# Bail out
			return []

	return [
		debian_package_build(
			suite,
			architecture,
			full_build=(architecture == first_arch),
			extra_repos=extra_repos,
			host_arch=host_arch
		)
		for architecture in build_on
		if architecture in SUPPORTED_ARCHITECTURES
	]


def main(context):
	return get_debian_package_pipelines(
		context,
		build_on=BUILD_ON,
		extra_repos=EXTRA_REPOS,
		host_arch=HOST_ARCH,
	)

