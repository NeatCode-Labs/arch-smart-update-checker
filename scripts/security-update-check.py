#!/usr/bin/env python3
"""
Security update checker for dependencies and system packages.
"""

# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

def check_python_dependencies() -> Dict[str, Any]:
    """Check Python dependencies for security vulnerabilities."""
    print("Checking Python dependencies...")
    
    try:
        # Run pip-audit
        result = subprocess.run(
            ["pip-audit", "--format", "json", "--desc"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            vulnerabilities = data.get("vulnerabilities", [])
            
            summary = {
                "total": len(vulnerabilities),
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "details": []
            }
            
            for vuln in vulnerabilities:
                name = vuln.get("name", "Unknown")
                version = vuln.get("version", "Unknown")
                
                for v in vuln.get("vulns", []):
                    severity = v.get("severity", "UNKNOWN").upper()
                    cve_id = v.get("id", "Unknown")
                    description = v.get("description", "No description")
                    
                    if severity in ["CRITICAL", "HIGH"]:
                        summary["critical" if severity == "CRITICAL" else "high"] += 1
                    elif severity == "MEDIUM":
                        summary["medium"] += 1
                    else:
                        summary["low"] += 1
                    
                    summary["details"].append({
                        "package": f"{name}=={version}",
                        "severity": severity,
                        "id": cve_id,
                        "description": description[:200]
                    })
            
            return summary
            
    except Exception as e:
        print(f"Error running pip-audit: {e}")
        return {"error": str(e)}

def check_system_packages() -> Dict[str, Any]:
    """Check system packages for security updates."""
    print("Checking system packages...")
    
    try:
        # Check for security updates using pacman
        result = subprocess.run(
            ["checkupdates"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            updates = result.stdout.strip().split('\n')
            return {
                "total_updates": len(updates),
                "packages": updates[:10]  # First 10 packages
            }
        else:
            return {"total_updates": 0, "packages": []}
            
    except Exception as e:
        print(f"Error checking system updates: {e}")
        return {"error": str(e)}

def check_cve_database() -> Dict[str, Any]:
    """Check for recent CVEs related to our stack."""
    print("Checking CVE database...")
    
    # This would normally query a CVE database API
    # For now, return a placeholder
    return {
        "last_checked": datetime.now().isoformat(),
        "status": "Manual check required",
        "recommendation": "Visit https://cve.mitre.org/ for latest CVEs"
    }

def generate_security_report(output_path: Optional[Path] = None) -> None:
    """Generate comprehensive security update report."""
    print("\n=== Security Update Report ===")
    print(f"Generated: {datetime.now().isoformat()}")
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "python_dependencies": check_python_dependencies(),
        "system_packages": check_system_packages(),
        "cve_status": check_cve_database()
    }
    
    # Print summary
    print("\n## Python Dependencies")
    py_deps = report["python_dependencies"]
    if "error" not in py_deps:
        print(f"Total vulnerabilities: {py_deps['total']}")
        print(f"- Critical: {py_deps.get('critical', 0)}")
        print(f"- High: {py_deps.get('high', 0)}")
        print(f"- Medium: {py_deps.get('medium', 0)}")
        print(f"- Low: {py_deps.get('low', 0)}")
        
        if py_deps["total"] > 0:
            print("\nTop vulnerabilities:")
            for detail in py_deps["details"][:5]:
                print(f"  - {detail['package']}: {detail['severity']} - {detail['id']}")
    else:
        print(f"Error: {py_deps['error']}")
    
    print("\n## System Packages")
    sys_pkgs = report["system_packages"]
    if "error" not in sys_pkgs:
        print(f"Total updates available: {sys_pkgs['total_updates']}")
        if sys_pkgs["total_updates"] > 0:
            print("Recent packages with updates:")
            for pkg in sys_pkgs["packages"][:5]:
                print(f"  - {pkg}")
    else:
        print(f"Error: {sys_pkgs['error']}")
    
    # Save report if path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report saved to: {output_path}")
    
    # Exit with error code if critical vulnerabilities found
    if py_deps.get("critical", 0) > 0 or py_deps.get("high", 0) > 0:
        print("\n⚠️  Critical/High severity vulnerabilities found!")
        sys.exit(1)

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Check for security updates")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output path for JSON report"
    )
    parser.add_argument(
        "--check-only", "-c",
        action="store_true",
        help="Only check, don't generate full report"
    )
    
    args = parser.parse_args()
    
    if args.check_only:
        # Quick check mode
        py_deps = check_python_dependencies()
        if py_deps.get("total", 0) > 0:
            print(f"Found {py_deps['total']} Python vulnerabilities")
            sys.exit(1)
        else:
            print("No Python vulnerabilities found")
            sys.exit(0)
    else:
        # Full report mode
        generate_security_report(args.output)

if __name__ == "__main__":
    main() 