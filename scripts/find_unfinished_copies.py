r"""Find unfinished copies in a media library (files that are mostly blank).

A copy that was interrupted can keep a valid header: ErsatzTV probes it, reads a
normal duration and schedules it, but everything after the first few megabytes is
zeros, so the channel shows nothing until that slot ends. On the disk such a file
has far less space allocated than its length. This script compares the two for
every video file. It reads metadata only, so 12,000 files take seconds.

Run it on the machine that holds the disk (not over SMB, which does not report
allocation). Works on ext4, xfs, zfs and ntfs-3g.

Usage:  python3 find_unfinished_copies.py <library_root> [threshold] > unfinished.tsv
        threshold = allocated/size below which a file is flagged (default 0.90)
Skips any folder that holds a .etvignore file (ErsatzTV skips those too).
Output: TSV on stdout (path, size, allocated, fraction); a summary on stderr.

What to do with the list: move the files out of the library (or into a folder with
a .etvignore), rescan, empty the trash, reset the playouts, then replace them with
good copies when you can. Never delete them on this script's word alone: a
compressed or deduplicated filesystem can also report a small allocation.
"""
import os, sys, collections

VIDEO = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".mpg", ".mpeg", ".ts",
         ".m2ts", ".webm", ".ogv", ".3gp", ".vob", ".flv", ".divx"}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.90
    total, flagged, groups = 0, 0, collections.Counter()
    print("path\tsize\tallocated\tfraction")
    for dirpath, dirnames, filenames in os.walk(root):
        if ".etvignore" in filenames:
            dirnames[:] = []
            continue
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in VIDEO:
                continue
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path)
            except OSError as e:
                print("stat failed: %s (%s)" % (path, e), file=sys.stderr)
                continue
            total += 1
            if st.st_size < 1024 * 1024:
                continue
            frac = st.st_blocks * 512 / st.st_size
            if frac < threshold:
                flagged += 1
                rel = os.path.relpath(dirpath, root).split(os.sep)
                groups[os.sep.join(rel[:2])] += 1
                print("%s\t%d\t%d\t%.3f" % (path, st.st_size, st.st_blocks * 512, frac))
    print("checked %d video files, %d look unfinished (allocated < %.0f%%)" % (total, flagged, threshold * 100), file=sys.stderr)
    for group, n in groups.most_common():
        print("  %5d  %s" % (n, group), file=sys.stderr)


if __name__ == "__main__":
    main()
