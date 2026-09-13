// Big Weather Windows bootstrapper. Build with scripts/build_windows_setup.py.
package main

import (
	"bufio"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

//go:embed payload.tar.gz
var payload []byte

//go:embed setup.ps1
var setupScript []byte

//go:embed setup-linux.sh
var linuxScript []byte

//go:embed launch.ps1
var launchScript []byte

func extract(directory string) error {
	if err := os.MkdirAll(directory, 0700); err != nil {
		return err
	}
	for name, data := range map[string][]byte{
		"payload.tar.gz": payload, "setup.ps1": setupScript,
		"setup-linux.sh": linuxScript, "launch.ps1": launchScript,
	} {
		if err := os.WriteFile(filepath.Join(directory, name), data, 0600); err != nil {
			return err
		}
	}
	return nil
}

func run() error {
	extractTo := flag.String("extract", "", "Extract installer files without running setup")
	flag.Parse()
	if *extractTo != "" {
		return extract(*extractTo)
	}
	if runtime.GOOS != "windows" {
		return errors.New("this setup program is for Windows; use --extract to inspect its contents")
	}
	fmt.Println("Big Weather setup for Windows 10/11 (64-bit)")
	fmt.Println("Installs WSL/Ubuntu, Python, Java, project packages and the bundled weather dataset.")
	fmt.Println("Internet access and about 8 GB free disk space are recommended.")
	fmt.Println("Windows may request administrator approval and a restart to enable WSL.")
	digest := sha256.Sum256(payload)
	hash := hex.EncodeToString(digest[:])
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		return errors.New("LOCALAPPDATA is not available")
	}
	directory := filepath.Join(base, "BigWeatherSetup", hash[:12])
	if err := extract(directory); err != nil {
		return err
	}
	powershell := filepath.Join(os.Getenv("SystemRoot"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
	command := exec.Command(powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
		filepath.Join(directory, "setup.ps1"), "-PackageDir", directory, "-PayloadHash", hash)
	command.Stdin, command.Stdout, command.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := command.Run(); err != nil {
		var exit *exec.ExitError
		if errors.As(err, &exit) && exit.ExitCode() == 3010 {
			return errors.New("restart Windows, then run this same setup EXE again to finish")
		}
		return fmt.Errorf("setup did not complete: %w. See setup.log in %s", err, directory)
	}
	return nil
}

func main() {
	err := run()
	if err != nil {
		fmt.Fprintln(os.Stderr, "\n", err)
	}
	if runtime.GOOS == "windows" {
		fmt.Println("\nPress Enter to close.")
		_, _ = bufio.NewReader(os.Stdin).ReadString('\n')
	}
	if err != nil {
		os.Exit(1)
	}
}
