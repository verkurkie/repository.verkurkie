# verkurkie.repository <!-- omit in toc -->
[![Build and Deploy](https://github.com/verkurkie/repository.verkurkie/actions/workflows/build_deploy.yml/badge.svg)](https://github.com/verkurkie/repository.verkurkie/actions/workflows/build_deploy.yml)

Kodi Repository for Verkurkie's Kodi add-ons.

## Table of Contents <!-- omit in toc -->

- [About](#about)
  - [Kodi](#kodi)
- [Installing the repo](#installing-the-repo)
  - [Add a file source to Kodi](#add-a-file-source-to-kodi)
  - [Turn on "Unknown sources" in Kodi:](#turn-on-unknown-sources-in-kodi)
  - [Install the repository:](#install-the-repository)
- [Installing add-ons from the repo](#installing-add-ons-from-the-repo)
  - [Install the add-on:](#install-the-add-on)
- [Resources](#resources)

## About

The repository is hosted on Github Pages at: <a href="https://verkurkie.github.io/repository.verkurkie" target="_blank" rel="noopener noreferrer">https://verkurkie.github.io/repository.verkurkie</a>

The repository is mainly for development & test purposes but glad to share & exchange ideas with the community!

### Kodi

<a href="https://kodi.tv" target="_blank" rel="noopener noreferrer">
  <img src="docs/kodi-logo-128x128.png" alt="Go to Kodi main site">
</a>

Kodi is a free and open source media player and entertainment hub for digital media. It is available for multiple operating systems, including Windows, macOS, Linux, iOS, and Android.

Download link: <a href="https://kodi.tv/download" target="_blank" rel="noopener noreferrer">https://kodi.tv/download</a>.

## Installing the repo

In case you didn't like the [Installing Kodi add-ons](https://www.cyberghostvpn.com/privacyhub/install-all-kodi-addons/) guide, here are the steps again:

### Add a file source to Kodi
1. Go to `Settings` -> `File manager` -> `Add source`
2. Click on the bar that has `<None>` in it
3. Enter the path `https://verkurkie.github.io/repository.verkurkie` and click `OK`
4. Name the source `verkurkie repo` or whatever you prefer and click `OK`

To validate, open the new source (double-click or press ENTER) and you should see the repository files

### Turn on "Unknown sources" in Kodi:
1. Go to `Settings` -> `System` -> `Add-ons`
2. Turn on `Unknown sources` and click `Yes`

### Install the repository:
1. Navigate to `Add-ons` in the Kodi home menu
2. Click on `Install from zip`
   - You should see a list of sources, incl. the one you created earlier
   - Click on `verkurkie repo` (or whatever you named it)
   - Click on the `repository.verkurkie-x.x.x.zip` file
   - After a brief moment, you should get a notification that the repository was installed successfully

## Installing add-ons from the repo

As an example, we'll be installing the "Xtream to M3U" add-on from the Verkurkie Repo:

### Install the add-on:

1. Navigate to `Add-ons` in the Kodi home menu
2. Click on "Install from repository"
   - Click on `Verkurkie Repo` (if it's not there, you need to install the repo first)
   - Click on `Program add-ons`
   - Click on `Xtream to M3U`
   - Click on `Install`
   - After a brief moment, you should get a notification that the add-on was installed successfully

To validate:
1. Navigate to `Add-ons` in the Kodi home menu
2. Click on `My add-ons`
3. As needed, navigate up/down and find `Program add-ons`
4. You should see the add-on in the list

## Resources

Kodi:

- <a href="https://kodi.tv" target="_blank" rel="noopener noreferrer">Kodi main website</a>
- <a href="https://www.cyberghostvpn.com/privacyhub/install-all-kodi-addons/" target="_blank" rel="noopener noreferrer">Installing Kodi add-ons</a>
- <a href="https://forum.kodi.tv" target="_blank" rel="noopener noreferrer">Kodi forum</a>

Inspiration for this repo:

- <a href="https://kodi.wiki/view/Add-on_repositories" target="_blank" rel="noopener noreferrer">Kodi Add-on repositories</a> (official docs)
- <a href="https://github.com/chadparry/kodi-repository.chad.parry.org/blob/master/README.md" target="_blank" rel="noopener noreferrer">chadparry/kodi-repository.chad.parry.org</a>
- <a href="https://raw.githubusercontent.com/chadparry/kodi-repository.chad.parry.org/master/tools/create_repository.py" target="_blank" rel="noopener noreferrer">chadparry/kodi-repository.chad.parry.org/tools/create_repository.py</a>
- <a href="https://github.com/drinfernoo/repository.example" target="_blank" rel="noopener noreferrer">drinfernoo/repository.example</a>
- <a href="https://github.com/peno64/repository.peno64" target="_blank" rel="noopener noreferrer">peno64/repository.peno64</a>
- <a href="https://github.com/peno64/repository.example/tree/master#" target="_blank" rel="noopener noreferrer">peno64/repository.example</a>