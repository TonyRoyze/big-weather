package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestExtract(t *testing.T) {
	directory := filepath.Join(t.TempDir(), "path with spaces")
	if err := extract(directory); err != nil {
		t.Fatal(err)
	}
	for name, expected := range map[string][]byte{
		"payload.tar.gz": payload, "setup.ps1": setupScript,
		"setup-linux.sh": linuxScript, "launch.ps1": launchScript,
	} {
		actual, err := os.ReadFile(filepath.Join(directory, name))
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(actual, expected) {
			t.Fatalf("incorrect bytes in %s", name)
		}
	}
}
