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
import time
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
    if os.name == 'nt':  # Only if we are running on Windows
        os.system("color")
        from ctypes import windll

        k = windll.kernel32
        console = k.SetConsoleMode(k.GetStdHandle(-11), 7)
        return console == 1
    return True


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


def cleanup():
    # Cleanup the root folder:
    # pe.cfg, *.bak, *.zip, /zips
    print("Cleaning up the root folder...")
    for file in os.listdir("."):
        if file.endswith(".bak") or file == "pe.cfg" or file.endswith(".zip"):
            print("- removing file: {}".format(color_text(file, 'red')))
            os.remove(file)
    if os.path.exists("zips"):
        print("- removing folder: {}".format(color_text("zips", 'red')))
        shutil.rmtree("zips")


def copy_repo_zip():
    # Copy the newly created repository ZIP file from zips/repository.verkurkie/ folder to the root folder
    # Note: the ZIP file name is unknown because it may have a new version number! Copy has to be for [repository.verkurkie*.zip]!

    # Use glob to find the file
    zip_file = glob.glob("zips/repository.verkurkie/*.zip")[0]
    md5_file = glob.glob("zips/repository.verkurkie/*.zip.md5")[0]

    if not zip_file:
        raise RuntimeError("No repository ZIP file found in zips/repository.verkurkie")
    if not md5_file:
        raise RuntimeError("No repository MD5 file found in zips/repository.verkurkie")
    
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


def user_confirm(msg, default="yes"):
    default = default.lower()
    default_yes = "[Y]es" if default == "yes" else "(y)es"
    default_no = "[N]o" if default == "no" else "(n)o"
    answers = "{} / {}".format(default_yes, default_no)
    try:
        user_input = input("{} {}: ".format(msg, answers))
        if user_input.lower() not in ["yes", "y", "no", "n"]:
            print(color_text("Invalid input. Please try again.", "red"))
            return user_confirm(msg, default)
    except (KeyboardInterrupt, EOFError):
        print(color_text("\nOperation cancelled.", "yellow"))
        sys.exit(0)

    answers_true = ["y", "yes"]
    if default == 'yes':
        answers_true.append("")
    return user_input.lower() in answers_true


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


def generate_indices():
    """
    Generates index.html files for the root and recursively for the zips folder.
    """
    release_path = '.'
    addon_path = os.path.join(release_path, "repo")
    zips_path = os.path.join(release_path, "zips")
    addons_xml_path = os.path.join(zips_path, "addons.xml")
    md5_path = os.path.join(zips_path, "addons.xml.md5")

    # 1. Recursive zips/ generation
    for root, dirs, files in os.walk(zips_path):
        # Sort for deterministic output
        dirs.sort()
        files.sort()

        # Skip writing to the directory if it doesn't exist (sanity check)
        if not os.path.exists(root):
            continue

        # Build list of items
        items = []
        
        # Add parent directory link
        rel_path = os.path.relpath(root, zips_path)
        items.append({
            "name": "../", 
            "href": "../", 
            "date": "-", 
            "size": "-"
        })

        # Add directories
        for d in dirs:
            path = os.path.join(root, d)
            stats = os.stat(path)
            mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(stats.st_mtime))
            items.append({
                "name": f"{d}/", 
                "href": f"{d}/", 
                "date": mtime, 
                "size": "-"
            })

        # Add files (excluding index.html)
        for f in files:
            if f == "index.html":
                continue
            path = os.path.join(root, f)
            stats = os.stat(path)
            mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(stats.st_mtime))
            size = str(stats.st_size)
            items.append({
                "name": f, 
                "href": f, 
                "date": mtime, 
                "size": size
            })

        # Determine title
        if rel_path == ".":
            title = "Index of /zips/"
        else:
            title = f"Index of /zips/{rel_path}/"
        
        # Write index.html
        index_path = os.path.join(root, "index.html")
        with open(index_path, "w") as f:
            f.write(_create_index_content(items, title=title))
        print(f"Updated index: {color_text(index_path, 'yellow')}")

    # 2. Generate ./index.html (Root)
    # We need to find the version of repository.verkurkie to link it correctly
    try:
        repo_xml_path = os.path.join(addon_path, "repository.verkurkie", "addon.xml")
        if os.path.exists(repo_xml_path):
            repo_xml = ElementTree.parse(repo_xml_path)
            version = repo_xml.getroot().get('version')
            
            root_index_path = "index.html"
            zip_file = f"repository.verkurkie-{version}.zip"
            md5_file = f"repository.verkurkie-{version}.zip.md5"
            
            # Helper to get stats for root items
            def get_root_item(name, href, is_dir=False):
                if is_dir:
                    path = href.rstrip('/') # remove trailing slash for stat
                    if os.path.exists(path):
                        stats = os.stat(path)
                        mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(stats.st_mtime))
                        return {"name": name, "href": href, "date": mtime, "size": "-"}
                elif os.path.exists(name):
                    stats = os.stat(name)
                    mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(stats.st_mtime))
                    size = str(stats.st_size)
                    return {"name": name, "href": href, "date": mtime, "size": size}
                return {"name": name, "href": href, "date": "-", "size": "-"}

            root_items = [
                get_root_item("zips/", "zips/", is_dir=True),
                get_root_item(zip_file, zip_file),
                get_root_item(md5_file, md5_file),
            ]
            
            with open(root_index_path, "w") as f:
                f.write(_create_index_content(root_items, title="Index of /"))
            print("Successfully updated {}".format(color_text(root_index_path, 'yellow')))
    except Exception as e:
        print(f"Error generating root index: {e}")

def _create_index_content(items, title="Index"):
    template = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>{title}</title>
</head>
<body>
<h1>{title}</h1>
<pre>
{header}
<hr>
{rows}
<hr>
</pre>
</body>
</html>"""
    # Calculate max length for Name column (min 50)
    max_len = 50
    for item in items:
        if len(item["name"]) > max_len:
            max_len = len(item["name"])
    
    # Add a little buffer
    name_width = max_len + 5
    date_width = 20
    size_width = 10

    # Header
    header = f'{"Name".ljust(name_width)}{"Last modified".ljust(date_width)}{"Size".rjust(size_width)}'

    # Rows
    rows = ""
    for item in items:
        name_cell = f'<a href="{item["href"]}">{item["name"]}</a>'.ljust(name_width + (len(f'<a href="{item["href"]}">{item["name"]}</a>') - len(item["name"])))
        # Logic above for ljust on HTML string is tricky because len() counts tags.
        # Easier way: constructs the plain text padded line, then replace Name with Link.
        
        line_fmt = f'{{name:<{name_width}}}{{date:<{date_width}}}{{size:>{size_width}}}'
        # But we can't easily reuse it because we need to inject the <a> tag around the name *before* padding? 
        # No, if we pad the LINK it messes up alignment relative to visible text.
        # We must pad the visible text, but output the link.
        # Standard way: <a href>Name</a> + spaces
        
        spaces = " " * (name_width - len(item["name"]))
        link = f'<a href="{item["href"]}">{item["name"]}</a>'
        row = f'{link}{spaces}{item["date"].ljust(date_width)}{item["size"].rjust(size_width)}'
        rows += row + "\n"
    
    return template.format(title=title, rows=rows, header=header)


def _save_file(data, file):
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

class Generator:
    """
    Generates a new addons.xml file from each addons addon.xml file
    and a new addons.xml.md5 hash file. Must be run from the root of
    the checked-out repo.
    """

    def __init__(self):
        self.release_path = ''
        self.addon_path = os.path.join(self.release_path, "repo")
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
        addon_folder = os.path.join(self.addon_path, folder)
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

                files_to_zip = []
                if os.path.isfile(item_path):
                    files_to_zip.append((item_path, os.path.join(addon_id, item)))
                elif os.path.isdir(item_path):
                    for root, dirs, files in os.walk(item_path):
                        dirs.sort()
                        if "__pycache__" in dirs:
                            dirs.remove("__pycache__")

                        for file in sorted(files):
                            file_path = os.path.join(root, file)
                            # Calculate arcname relative to the parent of item, then prefix with addon_id
                            rel_path = os.path.relpath(file_path, addon_folder)
                            arcname = os.path.join(addon_id, rel_path)
                            files_to_zip.append((file_path, arcname))

                for file_path, arcname in files_to_zip:
                    # Deterministic zip writing: fixed timestamp and permissions
                    zinfo = zipfile.ZipInfo(arcname)
                    zinfo.date_time = (2000, 1, 1, 0, 0, 0)
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    zinfo.external_attr = 0o100644 << 16  # -rw-r--r--

                    with open(file_path, "rb") as f:
                        zipf.writestr(zinfo, f.read())

        print("Successfully updated {}".format(color_text(final_zip, 'yellow')))

        # Create MD5 for the zip file
        self._generate_md5_file(final_zip, zip_md5_path)
        print("Successfully updated {}".format(color_text(zip_md5_path, 'yellow')))

    def _copy_meta_files(self, addon_id, addon_folder):
        """
        Copy the addon.xml and relevant art files into the relevant folders in the repository.
        """

        tree = ElementTree.parse(os.path.join(self.addon_path, addon_id, "addon.xml"))
        root = tree.getroot()

        copyfiles = ["addon.xml"]
        for ext in root.findall("extension"):
            if ext.get("point") in ["xbmc.addon.metadata", "kodi.addon.metadata"]:
                assets = ext.find("assets")
                if assets is None:
                    continue
                for art in [a for a in assets if a.text]:
                    copyfiles.append(os.path.normpath(art.text))

        src_folder = os.path.join(self.addon_path, addon_id)
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
            for i in os.listdir(self.addon_path)
            if os.path.isdir(os.path.join(self.addon_path, i))
            and i != "zips"
            and not i.startswith(".")
            and os.path.exists(os.path.join(self.addon_path, i, "addon.xml"))
        ]

        addon_xpath = "addon[@id='{}']"
        changed = False
        for addon in folders:
            try:
                addon_xml_path = os.path.join(self.addon_path, addon, "addon.xml")
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
            _save_file(m, file=md5_path)

            return True
        except Exception as e:
            print(
                "An error occurred updating {}!\n{}".format(
                    color_text(md5_path, 'yellow'), color_text(e, 'red')
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

    # Generate indices
    generate_indices()
