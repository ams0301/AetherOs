#!/bin/bash

# Create a temporary directory for testing
TEST_DIR="/tmp/aether-controller-test"
rm -rf $TEST_DIR
mkdir -p $TEST_DIR
cd $TEST_DIR

# Create some test files
echo "initial content" > file1.txt
echo "more data" > file2.txt
mkdir -p subdir
echo "subdir content" > subdir/file3.txt

# Initialize the controller (simulate by running the aether script)
cd /home/pc/.openclaw/workspace/aether-os/controller
OUTPUT_FILE="/tmp/controller_output.txt"

# Test snapshot creation
echo "Testing snapshot creation..."
python3 aether.py --workspace-dir $TEST_DIR snapshot --label "test-snapshot" > $OUTPUT_FILE 2>&1
cat $OUTPUT_FILE

# Check if snapshot was created
if [ -d "$TEST_DIR/snapshots/test-snapshot" ]; then
    echo "✅ Snapshot directory created"
else
    echo "❌ Snapshot directory not found"
fi

# Modify files to simulate changes
echo "changed content" > file1.txt
echo "new data" > file2.txt
echo "subdir changed" > subdir/file3.txt
echo "new file" > newfile.txt

# Test rewind
echo "Testing rewind to snapshot..."
python3 aether.py --workspace-dir $TEST_DIR rewind --steps 1 > $OUTPUT_FILE 2>&1
cat $OUTPUT_FILE

# Check if files were restored
if grep -q "initial content" $TEST_DIR/file1.txt && \
   grep -q "more data" $TEST_DIR/file2.txt && \
   grep -q "subdir content" $TEST_DIR/subdir/file3.txt && \
   [ ! -f $TEST_DIR/newfile.txt ]; then
    echo "✅ Files restored correctly from snapshot"
else
    echo "❌ Files not restored correctly"
    echo "file1.txt: $(cat $TEST_DIR/file1.txt)"
    echo "file2.txt: $(cat $TEST_DIR/file2.txt)"
    echo "subdir/file3.txt: $(cat $TEST_DIR/subdir/file3.txt 2>/dev/null || echo 'not found')"
    echo "newfile.txt: $(ls $TEST_DIR/newfile.txt 2>/dev/null && echo 'exists' || echo 'not found')"
fi

# Test list snapshots
echo "Testing list snapshots..."
python3 aether.py --workspace-dir $TEST_DIR list > $OUTPUT_FILE 2>&1
cat $OUTPUT_FILE

# Clean up
cd /tmp
rm -rf $TEST_DIR