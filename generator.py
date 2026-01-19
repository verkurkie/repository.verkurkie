import os
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
import argparse
import subprocess
import paramiko
import hashlib
import re
from dotenv import load_dotenv


def is_bump(v1, v2):
    """
    Compares two version strings using semantic versioning logic.
    Returns True if v1 > v2, False otherwise.
    """

    def parse_version(v):
        # Extract digits and dots, then split and convert to ints
        # This handles cases like 'v1.0.1' or '1.0.1b' by stripping non-numeric chars
        parts = []
        for part in re.split(r"[^0-9]+", v):
            if part:
                parts.append(int(part))
        return parts

    p1 = parse_version(v1)
    p2 = parse_version(v2)

    # Compare part by part
    for i in range(max(len(p1), len(p2))):
        val1 = p1[i] if i < len(p1) else 0
        val2 = p2[i] if i < len(p2) else 0
        if val1 > val2:
            return True
        if val1 < val2:
            return False
    return False


def generate_md5_file():
    """Create a new md5 hash"""
    import hashlib

    hexdigest = hashlib.md5(
        open("addons.xml", "r", encoding="utf-8").read().encode("utf-8")
    ).hexdigest()

    try:
        open("addons.xml.md5", "wb").write(hexdigest.encode("utf-8"))
    except Exception as exc:
        print("An error occurred creating addons.xml.md5 file!\n{}".format(exc))


def update_changelog(new_version, dry_run=False):
    print(f"Updating changelog.txt for version {new_version}...")

    # Get all commits since last tag
    try:
        # Check if current commit is already tagged (likely by PSR)
        is_tagged = (
            subprocess.run(
                ["git", "describe", "--tags", "--exact-match", "HEAD"],
                capture_output=True,
            ).returncode
            == 0
        )

        if is_tagged:
            # current commit is the tag, find the one before it
            last_tag = subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0", "HEAD^"],
                text=True,
                stderr=subprocess.STDOUT,
            ).strip()
        else:
            # current commit is not tagged, find the most recent tag
            last_tag = subprocess.check_output(
                ["git", "describe", "--tags", "--abbrev=0"],
                text=True,
                stderr=subprocess.STDOUT,
            ).strip()

        commit_range = f"{last_tag}..HEAD"
        print(f"Analyzing commits in range [{commit_range}] ...")
    except Exception:
        # No tags found, get all commits
        print("No tags found - analyzing all commits ...")
        commit_range = "HEAD"

    try:
        # --no-merges removes standard branch merge noise
        raw_commits = subprocess.check_output(
            ["git", "log", commit_range, "--no-merges", "--pretty=- %s"], text=True
        ).strip()

        # Patterns that should never appear in the changelog
        ignore_patterns = [
            "skip ci",
            "dependabot",
            "merged in",
            "Signed-off-by",
        ]

        commits = "\n".join(
            [
                c
                for c in raw_commits.split("\n")
                if c.strip()
                and not any(p.lower() in c.lower() for p in ignore_patterns)
            ]
        )
    except Exception:
        commits = "- Manual build/release"

    if not commits:
        commits = "- No changes recorded"

    new_entry = f"v{new_version}\n{commits}\n\n"

    # Use absolute path to ensure we are writing to the repo root in CI
    repo_root = os.path.dirname(os.path.abspath(__file__))
    changelog_path = os.path.join(repo_root, "changelog.txt")

    content = ""
    if os.path.exists(changelog_path):
        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()

    # Ensure we don't duplicate the version if it's already there
    if content.startswith(f"v{new_version}"):
        print(f"Changelog already has entry for {new_version}, skipping write.")
        return

    print(f"Writing new entry to {changelog_path}...")
    with open(changelog_path, "w", encoding="utf-8") as f:
        f.write(new_entry + content)

    # Verification for CI logs
    written_lines = new_entry.strip().split("\n")
    print(f"Successfully updated changelog. Latest entry: {written_lines[0]}")


def build_zip(addon_id, version, dry_run=False):
    zip_name = f"{addon_id}-{version}.zip"

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

    print(f"Building ZIP file [{zip_name}] ...")
    if dry_run:
        print(f"[DRY-RUN] Would create ZIP file [{zip_name}]")
        return

    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for item in includes:
            if not os.path.exists(item):
                print(f"Warning: [{item}] not found, skipping.")
                continue

            if os.path.isfile(item):
                arcname = os.path.join(addon_id, item)
                zipf.write(item, arcname=arcname)
            elif os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    if "__pycache__" in dirs:
                        dirs.remove("__pycache__")

                    for file in files:
                        file_path = os.path.join(root, file)
                        # Calculate arcname relative to the parent of item, then prefix with addon_id
                        rel_path = os.path.relpath(file_path)
                        arcname = os.path.join(addon_id, rel_path)
                        zipf.write(file_path, arcname=arcname)

    print(f"Successfully created ZIP file [{zip_name}]")


def generate_repo_files(external_addons={}, dry_run=False):
    """
    Generates addons.xml and addons.xml.md5
    Addons are collected from github repositories
    """
    print("Generating [addons.xml] and [addons.xml.md5] ...")

    addons_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<addons>\n'

    # Add repository itself (from root)
    if os.path.exists("addon.xml"):
        with open("addon.xml", "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r"(<addon.*?</addon>)", content, re.DOTALL)
            if match:
                addons_xml += match.group(1) + "\n\n"

    # Add external addons
    for addon_id, (github_username, use_token) in external_addons.items():
        # Convert the github url to raw user content
        raw_url = f"https://raw.githubusercontent.com/{github_username}/{addon_id}/main/addon.xml"

        print(f"Fetching [addon.xml] from [{raw_url}] using token: [{use_token}] ...")

        # Create a request object
        req = urllib.request.Request(raw_url)

        # Fetch the file using native python urllib
        # If use_token is true, use the `GH_TOKEN` or `GITHUB_TOKEN` variable from environment
        if use_token:
            token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
            if not token:
                raise ValueError(
                    "GH_TOKEN or GITHUB_TOKEN environment variable is not set"
                )
            # Headers are the correct way to pass a personal access token to GitHub
            req.add_header("Authorization", f"token {token}")

        try:
            with urllib.request.urlopen(req) as response:
                addon_xml = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            print(f"Error fetching {raw_url}: {e}")
            continue
        match = re.search(r"(<addon.*?</addon>)", addon_xml, re.DOTALL)
        if match:
            addons_xml += match.group(1) + "\n\n"

    addons_xml = addons_xml.strip() + "\n</addons>\n"

    if not dry_run:
        with open("addons.xml", "w", encoding="utf-8") as f:
            f.write(addons_xml)
        # Generate MD5
        m = hashlib.md5()
        with open("addons.xml", "rb") as f:
            m.update(f.read())

        with open("addons.xml.md5", "w") as f:
            f.write(m.hexdigest())
    else:
        print("[DRY-RUN] Would write [addons.xml] and [addons.xml.md5] files.")


def transfer_to_kodi_repository(new_version, dry_run=False):
    if dry_run:
        print("[DRY-RUN] Would transfer files to [verkurkie.com] via SFTP...")
        return

    print("Starting FTP transfer...")
    # Get the host, user, pass from environment variables
    ftp_host = os.getenv("FTP_HOST")
    ftp_user = os.getenv("FTP_USER")
    ftp_pass = os.getenv("FTP_PASS")
    ftp_base_dir = "/home/verkurkie/public_html/kodi"
    addon_id = "repository.verkurkie"
    zip_file = f"{addon_id}-{new_version}.zip"

    if not ftp_host or not ftp_user or not ftp_pass:
        print("SFTP credentials not found in environment variables. Aborting!")
        return

    try:
        # Transfer the files
        print(f"Connecting to FTP server [{ftp_host}] via SFTP...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ftp_host, username=ftp_user, password=ftp_pass)
        sftp = ssh.open_sftp()

        # Go to base dir
        try:
            sftp.chdir(ftp_base_dir)
        except IOError:
            print(f"- directory [{ftp_base_dir}] not found on server. Aborting!")
            return

        # Ensure the `repo` and `zips` directories exist
        print("- checking directory structure...")
        try:
            sftp.mkdir("repo")
        except IOError:
            pass  # Already exists
        try:
            sftp.mkdir("zips")
        except IOError:
            pass  # Already exists
        addon_dir = f"zips/{addon_id}"
        try:
            sftp.mkdir(addon_dir)
        except IOError:
            pass  # Already exists

        # Transfer the addon files

        # Upload files to the /repo folder
        print(f"- uploading ZIP file [{zip_file}] to [/repo] folder ...")
        sftp.put(f"{zip_file}", f"repo/{zip_file}")

        # Upload root files to the /zips folder
        print("- uploading root files to [/zips] folder ...")
        sftp.put("addons.xml", "zips/addons.xml")
        sftp.put("addons.xml.md5", "zips/addons.xml.md5")
        sftp.put("icon.png", "zips/icon.png")
        sftp.put("fanart.jpg", "zips/fanart.jpg")

        # Upload addon files to the /zips/{addon_id} folder
        print("- uploading addon files to [/zips/{addon_id}] folder ...")
        sftp.put(f"{zip_file}", f"{addon_dir}/{zip_file}")
        sftp.put("addon.xml", f"{addon_dir}/addon.xml")
        sftp.put("icon.png", f"{addon_dir}/icon.png")
        sftp.put("fanart.jpg", f"{addon_dir}/fanart.jpg")

        print("- closing connection ...")
        sftp.close()
        ssh.close()
        print("SFTP transfer complete.")
    except Exception as e:
        print(f"SFTP transfer failed: {e}")


def main():
    # Set the environment variables from the .env file
    load_dotenv()

    parser = argparse.ArgumentParser(description="Build and version Kodi Repository")
    parser.add_argument("--version", help="New repository version number to set")
    parser.add_argument("--zip", action="store_true", help="Only create the ZIP file")
    parser.add_argument("--dry-run", action="store_true", help="Do not write any files")
    parser.add_argument(
        "--transfer", action="store_true", help="Transfer files to Kodi repository"
    )
    parser.add_argument(
        "--generate", action="store_true", help="Only generate repository files"
    )
    parser.add_argument(
        "--changelog", action="store_true", help="Only update changelog.txt"
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and not args.zip
        and not args.transfer
        and not args.generate
        and not args.changelog
    ):
        print(
            "the [--dry-run] flag requires [--zip] or [--transfer] or [--generate] or [--changelog] flag(s)"
        )
        return

    # Get current/new version info
    tree = ET.parse("addon.xml")
    root = tree.getroot()
    repo_id = root.get("id")
    current_version = root.get("version")

    new_version = (
        args.version
        if (args.version and args.version != current_version)
        else current_version
    )

    # External addons configuration
    external_addons = {"script.iptv.xtream-to-m3u": ("verkurkie", True)}

    if args.generate:
        generate_repo_files(external_addons, args.dry_run)
        return

    if args.changelog:
        update_changelog(new_version, args.dry_run)
        return

    # In CI (post-PSR bump), the versions will match. We must still run the build.
    if args.zip or args.transfer:
        # Update changelog
        update_changelog(new_version, args.dry_run)
        
        if args.zip:
            build_zip(repo_id, new_version, args.dry_run)

        if args.transfer:
            # Refresh ignored repository files (addons.xml) before transfer
            generate_repo_files(external_addons, args.dry_run)
            transfer_to_kodi_repository(new_version, args.dry_run)


if __name__ == "__main__":
    main()
