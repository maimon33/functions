import sys

if __name__ == '__main__':
    arg = sys.argv[1]
    if arg == 'restore':
        load_snapshot_and_restore()
        sys.exit()
    else:
        SNAPSHOT_ID = create_snapshot()
        get_snapshot_and_upload(SNAPSHOT_ID)