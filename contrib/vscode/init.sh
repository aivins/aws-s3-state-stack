#!/bin/sh

# Create .vscode settings for VSCode users
# Borrowed idea from https://github.com/git/git/blob/master/contrib/vscode/init.sh

die () {
	echo "$*" >&2
	exit 1
}

cd "$(dirname "$0")"/../.. ||
die "Could not cd to top-level directory"

mkdir -p .vscode ||
die "Could not create .vscode/"


for file in settings.json extensions.json launch.json
do
  cat $(dirname "$0")/$file >.vscode/$file.new || die "Could not write $file"
	if test -f .vscode/$file
	then
		if git diff --no-index --quiet --exit-code .vscode/$file .vscode/$file.new
		then
			rm .vscode/$file.new
		else
			printf "The file .vscode/$file.new has these changes:\n\n"
			git --no-pager diff --no-index .vscode/$file .vscode/$file.new
			printf "\n\nMaybe \`mv .vscode/$file.new .vscode/$file\`?\n\n"
		fi
	else
		mv .vscode/$file.new .vscode/$file
	fi
done
