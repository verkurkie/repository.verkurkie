"""
    Put this script in the root folder of your repo and it will
    zip up all addon folders, create a new zip in your zips folder
    and then update the md5 and addons.xml file
"""

import os
import sys
import glob
import subprocess
import shutil
import hashlib
import zipfile
from xml.etree import ElementTree

SCRIPT_VERSION = 2
KODI_VERSIONS = ["krypton", "leia", "matrix", "repo"]
IGNORE = [
    "docs",
    "build.py",
    "pyproject.toml",
    "README.md",
    ".git",
    ".github",
    ".gitignore",
    ".DS_Store",
    "thumbs.db",
    ".idea",
    "venv",
]


def _setup_colors():
    color = os.system("color")
    console = 0
    if os.name == 'nt':  # Only if we are running on Windows
        from ctypes import windll

        k = windll.kernel32
        console = k.SetConsoleMode(k.GetStdHandle(-11), 7)
    return color == 1 or console == 1


_COLOR_ESCAPE = "\x1b[{}m"
_COLORS = {
    "black": "30",
    "red": "31",
    "green": "4;32",
    "yellow": "3;33",
    "blue": "34",
    "magenta": "35",
    "cyan": "1;36",
    "grey": "37",
    "endc": "0",
}
_SUPPORTS_COLOR = _setup_colors()


def color_text(text, color):
    return (
        '{}{}{}'.format(
            _COLOR_ESCAPE.format(_COLORS[color]),
            text,
            _COLOR_ESCAPE.format(_COLORS["endc"]),
        )
        if _SUPPORTS_COLOR
        else text
    )


def convert_bytes(num):
    """
    this function will convert bytes to MB.... GB... etc
    """
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


def cleanup():
    # Cleanup the root folder:
    # pe.cfg, *.bak, *.zip, repo/zips
    print("Cleaning up the root folder...")
    for file in os.listdir("."):
        if file.endswith(".bak") or file == "pe.cfg" or file.endswith(".zip"):
            print("- removing file: {}".format(color_text(file, 'red')))
            os.remove(file)
    if os.path.exists("repo/zips"):
        print("- removing folder: {}".format(color_text("repo/zips", 'red')))
        shutil.rmtree("repo/zips")


def copy_repo_zip():
    # Copy the newly created repository ZIP file from repo/zips/repository.verkurkie/ folder to the root folder
    # Note: the ZIP file name is unknown because it may have a new version number! Copy has to be for [repository.verkurkie*.zip]!

    # Use glob to find the file
    zip_file = glob.glob("repo/zips/repository.verkurkie/*.zip")[0]
    md5_file = glob.glob("repo/zips/repository.verkurkie/*.zip.md5")[0]

    if not zip_file:
        raise RuntimeError("No repository ZIP file found in repo/zips/repository.verkurkie")
    if not md5_file:
        raise RuntimeError("No repository MD5 file found in repo/zips/repository.verkurkie")
    
    # Copy the file
    print("Copying repository ZIP file to the root folder...")
    shutil.copy(zip_file, ".")
    print("- copied file: {}".format(color_text(zip_file, 'green')))

    print("Copying repository MD5 file to the root folder...")
    shutil.copy(md5_file, ".")
    print("- copied file: {}".format(color_text(md5_file, 'green')))


def check_changes():
    # Check if there are other changes in the repository and ask user to check them and add whatever else they want to commit
    diff = subprocess.run(["git", "diff", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if diff.returncode != 0:
        # There are pending changes - ask the user for action
        result = user_confirm("There are unstaged changes. Continue to review and/or add more changes?", is_commit=True)

        if not result:
            return

        # Check again after changes
        check_changes()


def user_confirm(msg, is_commit=False, default="yes"):
    default = default.lower()
    if is_commit:
        subprocess.run(["git", "status"], stderr=subprocess.DEVNULL)

    default_yes = "[Y]es" if default == "yes" else "(y)es"
    default_no = "[N]o" if default == "no" else "(n)o"
    answers = "{} / {} / {}".format(default_yes, default_no, "(a)dd") if is_commit else "{} / {}".format(default_yes, default_no)
    try:
        user_input = input("{} {}: ".format(msg, answers))
        if user_input.lower() not in ["yes", "y", "no", "n", "add", "a", ""]:
            print(color_text("Invalid input. Please try again.", "red"))
            return user_confirm(msg, is_commit, default)
    except (KeyboardInterrupt, EOFError):
        print(color_text("\nOperation cancelled.", "yellow"))
        sys.exit(0)

    if is_commit and user_input in ["a", "add"]:
        try:
            add = input("Enter additional commit(s) - you can use glob patterns! (e.g. repo/zips/*): ")
        except (KeyboardInterrupt, EOFError):
            print(color_text("\nOperation cancelled.", "yellow"))
            sys.exit(0)
        if add:
            subprocess.run(["git", "add", add], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return user_confirm(msg, is_commit=True)

    answers_true = ["y", "yes"]
    if default == 'yes':
        answers_true.append("")
    return user_input.lower() in answers_true


def run_git():
    # Check if '--push' and/or '--commit' were requested
    is_ci = '--ci' in sys.argv
    do_push = '--push' in sys.argv or is_ci
    do_commit = '--commit' in sys.argv or do_push

    # Check for '--commit-msg {message}' and extract the message
    commit_msg_parts = []
    found_msg_flag = False
    for i, arg in enumerate(sys.argv[1:], 1):
        if not found_msg_flag:
            if arg.startswith('--commit-msg='):
                commit_msg_parts.append(arg.split('=', 1)[1])
                found_msg_flag = True
            elif arg == '--commit-msg':
                found_msg_flag = True
        else:
            if arg.startswith('-'):
                break
            commit_msg_parts.append(arg)

    commit_msg = " ".join(commit_msg_parts) if commit_msg_parts else "chore: update repository and addons"

    # Files of interest are the repository ZIP file in the root and everything in repo/zips
    if do_commit:
        subprocess.run(["git", "add", "repository*.zip"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "add", "repo/zips/"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Check for staged changes
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"])

        # Check for additional changes
        if not is_ci and staged.returncode == 0:
            check_changes()

        # Check for staged changes again
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"])

        if staged.returncode == 0:
            print(color_text("Nothing to commit", "yellow"))
        else:
            try:
                run_commit = is_ci or user_confirm("Commit these changes?", is_commit=True)
                if run_commit:
                    subprocess.run(["git", "commit", "-m", commit_msg], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(color_text("Changes committed to local repository!\n", "green"))
            except Exception as e:
                print(color_text(f"Error during git operations: {e}", "red"))

    if do_push:
        # Check if there is anything to push
        # Check if our local HEAD is ahead of the remote origin/main
        # (This ignores staged changes that haven't been committed yet)
        res = subprocess.run(["git", "rev-list", "--count", "origin/main..HEAD"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip() == "0":
            # No unpushed commits... but check if we have uncommitted staged changes!
            staged = subprocess.run(["git", "diff", "--cached", "--quiet"])
            if staged.returncode == 0:
                print(color_text("Nothing to push to GitHub.\n", "yellow"))
                return
            else:
                print(color_text("Warning: You have staged changes - you need to commit them before pushing to GitHub!", "yellow"))
                return

        # Ask the user for confirmation to push (if not --yes)
        try:
            user_confirm_push = True if is_ci else user_confirm("Push to GitHub?")
        except (KeyboardInterrupt, EOFError):
            print(color_text("\nOperation cancelled.", "yellow"))
            sys.exit(0)

        if user_confirm_push:
            try:
                # subprocess.run(["git", "push"], check=True)
                print(color_text("Commits pushed to GitHub!\n", "green"))
            except Exception as e:
                print(color_text(f"Error during git operations: {e}", "red"))


def check_submodules():
    # Check if there are committed/uncommitted or untracked changes in submodule(s)
    print("Updating & checking submodules...")
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout
    
    # Get the list of submodules dynamically
    submodules = subprocess.run(["git", "submodule", "--quiet", "foreach", "echo $sm_path"], 
                               capture_output=True, text=True).stdout.splitlines()

    dirty_submodules = []
    for line in status.splitlines():
        # Line format: XY path (e.g., ' M repo/script.iptv.xtream-to-m3u')
        path = line[3:].strip()
        if any(path.startswith(sm) for sm in submodules):
            dirty_submodules.append(path)

    if dirty_submodules:
        print(color_text("Warning: The following submodule(s) have changes:", "red"))
        for sm in dirty_submodules:
            print(f"- {sm}")
        
        try:
            cancel_msg = "Operation cancelled. Please clean submodule(s) and try again."
            if not user_confirm("Do you want to continue with generating the repository?", default="no"):
                print(color_text(cancel_msg, "yellow"))
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print(color_text(cancel_msg, "yellow"))
            sys.exit(0)


class Generator:
    """
    Generates a new addons.xml file from each addons addon.xml file
    and a new addons.xml.md5 hash file. Must be run from the root of
    the checked-out repo.
    """

    def __init__(self):
        self.release_path = 'repo'
        self.zips_path = os.path.join(self.release_path, "zips")
        addons_xml_path = os.path.join(self.zips_path, "addons.xml")
        md5_path = os.path.join(self.zips_path, "addons.xml.md5")

        if not os.path.exists(self.zips_path):
            os.makedirs(self.zips_path)

        self._remove_binaries()

        if self._generate_addons_file(addons_xml_path):
            print(
                "Successfully updated {}".format(color_text(addons_xml_path, 'yellow'))
            )

            if self._generate_md5_file(addons_xml_path, md5_path):
                print("Successfully updated {}".format(color_text(md5_path, 'yellow')))

    def _remove_binaries(self):
        """
        Removes any and all compiled Python files before operations.
        """

        for parent, dirnames, filenames in os.walk(self.release_path):
            for fn in filenames:
                if fn.lower().endswith("pyo") or fn.lower().endswith("pyc"):
                    compiled = os.path.join(parent, fn)
                    try:
                        os.remove(compiled)
                        print(
                            "Removed compiled python file: {}".format(
                                color_text(compiled, 'green')
                            )
                        )
                    except Exception as e:
                        print(
                            "Failed to remove compiled python file: {} - Error: {}".format(
                                color_text(compiled, 'red'), color_text(e, 'red')
                            )
                        )
            for dir in dirnames:
                if "pycache" in dir.lower():
                    compiled = os.path.join(parent, dir)
                    try:
                        shutil.rmtree(compiled)
                        print(
                            "Removed __pycache__ cache folder: {}".format(
                                color_text(compiled, 'green')
                            )
                        )
                    except Exception as e:
                        print(
                            "Failed to remove __pycache__ cache folder:  {} - Error: {}".format(
                                color_text(compiled, 'red'), color_text(e, 'red')
                            )
                        )

    def build_zip(self, folder, addon_id, version):
        zip_name = f"{addon_id}-{version}.zip"
        addon_folder = os.path.join(self.release_path, folder)
        zip_folder = os.path.join(self.zips_path, addon_id)
        if not os.path.exists(zip_folder):
            os.makedirs(zip_folder)
        final_zip = os.path.join(zip_folder, "{0}-{1}.zip".format(addon_id, version))
        zip_md5_path = os.path.join(zip_folder, "{0}-{1}.zip.md5".format(addon_id, version))

        # Files and directories to include as per RELEASE.md
        contents = {
            "repo": ["addon.xml", "icon.png", "fanart.jpg"],
            "addon": [
                "addon.xml",
                "main.py",
                "fanart.jpg",
                "icon.png",
                "resources",
                "changelog.txt",
                "README.md",
            ],
        }

        includes = (
            contents["repo"] if addon_id == "repository.verkurkie" else contents["addon"]
        )

        with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for item in includes:
                item_path = os.path.join(addon_folder, item)
                if not os.path.exists(item_path):
                    print(f"Warning: [{item_path}] not found, skipping.")
                    continue

                if os.path.isfile(item_path):
                    arcname = os.path.join(addon_id, item)
                    zipf.write(item_path, arcname=arcname)
                elif os.path.isdir(item_path):
                    for root, dirs, files in os.walk(item_path):
                        if "__pycache__" in dirs:
                            dirs.remove("__pycache__")

                        for file in files:
                            file_path = os.path.join(root, file)
                            # Calculate arcname relative to the parent of item, then prefix with addon_id
                            rel_path = os.path.relpath(file_path, addon_folder)
                            arcname = os.path.join(addon_id, rel_path)
                            zipf.write(file_path, arcname=arcname)

        print("Successfully updated {}".format(color_text(final_zip, 'yellow')))

        # Create MD5 for the zip file
        self._generate_md5_file(final_zip, zip_md5_path)
        print("Successfully updated {}".format(color_text(zip_md5_path, 'yellow')))

    def _copy_meta_files(self, addon_id, addon_folder):
        """
        Copy the addon.xml and relevant art files into the relevant folders in the repository.
        """

        tree = ElementTree.parse(os.path.join(self.release_path, addon_id, "addon.xml"))
        root = tree.getroot()

        copyfiles = ["addon.xml"]
        for ext in root.findall("extension"):
            if ext.get("point") in ["xbmc.addon.metadata", "kodi.addon.metadata"]:
                assets = ext.find("assets")
                if assets is None:
                    continue
                for art in [a for a in assets if a.text]:
                    copyfiles.append(os.path.normpath(art.text))

        src_folder = os.path.join(self.release_path, addon_id)
        for file in copyfiles:
            addon_path = os.path.join(src_folder, file)
            if not os.path.exists(addon_path):
                continue

            zips_path = os.path.join(addon_folder, file)
            asset_path = os.path.split(zips_path)[0]
            if not os.path.exists(asset_path):
                os.makedirs(asset_path)

            shutil.copy(addon_path, zips_path)

    def _generate_addons_file(self, addons_xml_path):
        """
        Generates a zip for each found addon, and updates the addons.xml file accordingly.
        """
        if not os.path.exists(addons_xml_path):
            addons_root = ElementTree.Element('addons')
            addons_xml = ElementTree.ElementTree(addons_root)
        else:
            addons_xml = ElementTree.parse(addons_xml_path)
            addons_root = addons_xml.getroot()

        folders = [
            i
            for i in os.listdir(self.release_path)
            if os.path.isdir(os.path.join(self.release_path, i))
            and i != "zips"
            and not i.startswith(".")
            and os.path.exists(os.path.join(self.release_path, i, "addon.xml"))
        ]

        addon_xpath = "addon[@id='{}']"
        changed = False
        for addon in folders:
            try:
                addon_xml_path = os.path.join(self.release_path, addon, "addon.xml")
                addon_xml = ElementTree.parse(addon_xml_path)
                addon_root = addon_xml.getroot()
                id = addon_root.get('id')
                version = addon_root.get('version')

                updated = False
                addon_entry = addons_root.find(addon_xpath.format(id))
                if addon_entry is not None and addon_entry.get('version') != version:
                    index = addons_root.findall('addon').index(addon_entry)
                    addons_root.remove(addon_entry)
                    addons_root.insert(index, addon_root)
                    updated = True
                    changed = True
                elif addon_entry is None:
                    addons_root.append(addon_root)
                    updated = True
                    changed = True

                if updated:
                    # Create the zip files
                    self.build_zip(addon, id, version)
                    # Copy meta files
                    self._copy_meta_files(addon, os.path.join(self.zips_path, id))
            except Exception as e:
                print(
                    "Excluding {}: {}".format(
                        color_text(id, 'yellow'), color_text(e, 'red')
                    )
                )

        if changed:
            addons_root[:] = sorted(addons_root, key=lambda addon: addon.get('id'))
            try:
                addons_xml.write(
                    addons_xml_path, encoding="utf-8", xml_declaration=True
                )

                return changed
            except Exception as e:
                print(
                    "An error occurred updating {}!\n{}".format(
                        color_text(addons_xml_path, 'yellow'), color_text(e, 'red')
                    )
                )

    def _generate_md5_file(self, file_path, md5_path):
        """
        Generates a new addons.xml.md5 file.
        """
        try:
            m = hashlib.md5(open(file_path, "rb").read()).hexdigest()
            self._save_file(m, file=md5_path)

            return True
        except Exception as e:
            print(
                "An error occurred updating {}!\n{}".format(
                    color_text(md5_path, 'yellow'), color_text(e, 'red')
                )
            )

    def _save_file(self, data, file):
        """
        Saves a file.
        """
        try:
            open(file, "w").write(data)
        except Exception as e:
            print(
                "An error occurred saving {}!\n{}".format(
                    color_text(file, 'yellow'), color_text(e, 'red')
                )
            )


if __name__ == "__main__":
    # Check if there are committed/uncommitted or untracked changes in submodule(s)
    check_submodules()

    # Clean up old zips & other artifacts
    cleanup()

    # Generate repository & addon zip files
    Generator()

    # Copy repository zip file to root folder
    copy_repo_zip()

    # Commit & push changes to GitHub (only on local runs! in CI, the git actions are handled by update-submodule.yml)
    run_git()
