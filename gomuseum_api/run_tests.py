#!/usr/bin/env python3
"""
Test runner script for GoMuseum API
Provides comprehensive testing with detailed reporting
"""
import subprocess
import sys
import os
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any
import json


class TestRunner:
    """Test runner with comprehensive reporting"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.test_results = {}
        self.start_time = None
        self.end_time = None
    
    def run_command(self, command: List[str], description: str) -> Dict[str, Any]:
        """Run a command and capture results"""
        print(f"\n{'='*60}")
        print(f"运行: {description}")
        print(f"命令: {' '.join(command)}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            return {
                "success": result.returncode == 0,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": " ".join(command),
                "description": description
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "duration": 600,
                "stdout": "",
                "stderr": "测试超时 (10分钟)",
                "returncode": -1,
                "command": " ".join(command),
                "description": description
            }
        except Exception as e:
            return {
                "success": False,
                "duration": 0,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "command": " ".join(command),
                "description": description
            }
    
    def run_unit_tests(self) -> Dict[str, Any]:
        """Run unit tests"""
        command = [
            "python", "-m", "pytest",
            "tests/unit/",
            "-v",
            "--tb=short",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/unit",
            "--cov-report=xml:coverage_unit.xml",
            "--junit-xml=junit_unit.xml",
            "-m", "unit"
        ]
        
        return self.run_command(command, "单元测试")
    
    def run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests"""
        command = [
            "python", "-m", "pytest",
            "tests/integration/",
            "-v",
            "--tb=short",
            "--junit-xml=junit_integration.xml",
            "-m", "integration"
        ]
        
        return self.run_command(command, "集成测试")
    
    def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance tests"""
        command = [
            "python", "-m", "pytest",
            "tests/performance/",
            "-v",
            "--tb=short",
            "--junit-xml=junit_performance.xml",
            "-m", "performance"
        ]
        
        return self.run_command(command, "性能测试")
    
    def run_security_tests(self) -> Dict[str, Any]:
        """Run security tests"""
        command = [
            "python", "-m", "pytest",
            "tests/security/",
            "-v",
            "--tb=short",
            "--junit-xml=junit_security.xml",
            "-m", "security"
        ]
        
        return self.run_command(command, "安全测试")
    
    def run_e2e_tests(self) -> Dict[str, Any]:
        """Run end-to-end tests"""
        command = [
            "python", "-m", "pytest",
            "tests/e2e/",
            "-v",
            "--tb=short",
            "--junit-xml=junit_e2e.xml",
            "-m", "e2e"
        ]
        
        return self.run_command(command, "端到端测试")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests"""
        command = [
            "python", "-m", "pytest",
            "tests/",
            "-v",
            "--tb=short",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov/all",
            "--cov-report=xml:coverage_all.xml",
            "--junit-xml=junit_all.xml",
            "--durations=10",
            "--maxfail=5"
        ]
        
        return self.run_command(command, "所有测试")
    
    def run_specific_tests(self, test_path: str) -> Dict[str, Any]:
        """Run specific tests"""
        command = [
            "python", "-m", "pytest",
            test_path,
            "-v",
            "--tb=short"
        ]
        
        return self.run_command(command, f"特定测试: {test_path}")
    
    def run_linting(self) -> Dict[str, Any]:
        """Run code linting"""
        results = {}
        
        # Black formatting check
        black_result = self.run_command(
            ["python", "-m", "black", "--check", "--diff", "app/", "tests/"],
            "代码格式检查 (Black)"
        )
        results["black"] = black_result
        
        # isort import sorting check
        isort_result = self.run_command(
            ["python", "-m", "isort", "--check-only", "--diff", "app/", "tests/"],
            "导入排序检查 (isort)"
        )
        results["isort"] = isort_result
        
        # MyPy type checking
        mypy_result = self.run_command(
            ["python", "-m", "mypy", "app/"],
            "类型检查 (MyPy)"
        )
        results["mypy"] = mypy_result
        
        return results
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate test report"""
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        report = []
        report.append("=" * 80)
        report.append("GoMuseum API 测试报告")
        report.append("=" * 80)
        report.append(f"总耗时: {total_duration:.2f} 秒")
        report.append("")
        
        # Summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results.values() if isinstance(r, dict) and r.get("success", False))
        failed_tests = total_tests - passed_tests
        
        report.append("测试总结:")
        report.append(f"  总测试套件: {total_tests}")
        report.append(f"  通过: {passed_tests}")
        report.append(f"  失败: {failed_tests}")
        report.append(f"  成功率: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "  成功率: N/A")
        report.append("")
        
        # Detailed results
        report.append("详细结果:")
        report.append("-" * 40)
        
        for test_name, result in results.items():
            if isinstance(result, dict):
                status = "✅ 通过" if result.get("success", False) else "❌ 失败"
                duration = result.get("duration", 0)
                
                report.append(f"{test_name}: {status} ({duration:.2f}s)")
                
                if not result.get("success", False) and result.get("stderr"):
                    report.append(f"  错误: {result['stderr'][:200]}...")
            else:
                # Handle nested results (like linting)
                report.append(f"{test_name}:")
                for sub_test, sub_result in result.items():
                    status = "✅ 通过" if sub_result.get("success", False) else "❌ 失败"
                    duration = sub_result.get("duration", 0)
                    report.append(f"  {sub_test}: {status} ({duration:.2f}s)")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_report(self, report: str, filename: str = "test_report.txt"):
        """Save report to file"""
        report_path = self.project_root / filename
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n测试报告已保存至: {report_path}")
    
    def print_performance_summary(self, results: Dict[str, Any]):
        """Print performance test summary"""
        perf_result = results.get("performance")
        if not perf_result:
            return
        
        print("\n" + "="*60)
        print("性能测试总结")
        print("="*60)
        
        if perf_result.get("success"):
            print("✅ 性能测试通过")
            print("关键指标:")
            print("  - API 响应时间: < 100ms (95%)")
            print("  - 缓存响应时间: < 10ms")
            print("  - 数据库查询时间: < 50ms")
            print("  - 内存使用: < 100MB")
        else:
            print("❌ 性能测试失败")
            print("请检查性能瓶颈")
    
    def print_security_summary(self, results: Dict[str, Any]):
        """Print security test summary"""
        sec_result = results.get("security")
        if not sec_result:
            return
        
        print("\n" + "="*60)
        print("安全测试总结")
        print("="*60)
        
        if sec_result.get("success"):
            print("✅ 安全测试通过")
            print("已验证:")
            print("  - SQL 注入防护")
            print("  - XSS 防护")
            print("  - 认证安全")
            print("  - 输入验证")
            print("  - 路径遍历防护")
        else:
            print("❌ 发现安全漏洞")
            print("⚠️  请立即修复安全问题")


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="GoMuseum API 测试运行器")
    parser.add_argument("--type", choices=["unit", "integration", "performance", "security", "e2e", "all", "lint"], 
                       default="all", help="要运行的测试类型")
    parser.add_argument("--path", help="运行特定路径的测试")
    parser.add_argument("--no-report", action="store_true", help="不生成测试报告")
    parser.add_argument("--fast", action="store_true", help="快速模式，跳过慢速测试")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    runner.start_time = time.time()
    
    print("🚀 启动 GoMuseum API 测试套件")
    print(f"测试类型: {args.type}")
    
    results = {}
    
    try:
        if args.path:
            # Run specific test path
            results["specific"] = runner.run_specific_tests(args.path)
        
        elif args.type == "unit":
            results["unit"] = runner.run_unit_tests()
        
        elif args.type == "integration":
            results["integration"] = runner.run_integration_tests()
        
        elif args.type == "performance":
            if not args.fast:
                results["performance"] = runner.run_performance_tests()
            else:
                print("⏩ 快速模式: 跳过性能测试")
        
        elif args.type == "security":
            results["security"] = runner.run_security_tests()
        
        elif args.type == "e2e":
            if not args.fast:
                results["e2e"] = runner.run_e2e_tests()
            else:
                print("⏩ 快速模式: 跳过端到端测试")
        
        elif args.type == "lint":
            results["linting"] = runner.run_linting()
        
        elif args.type == "all":
            # Run linting first
            results["linting"] = runner.run_linting()
            
            # Run all test types
            results["unit"] = runner.run_unit_tests()
            results["integration"] = runner.run_integration_tests()
            
            if not args.fast:
                results["performance"] = runner.run_performance_tests()
                results["security"] = runner.run_security_tests()
                results["e2e"] = runner.run_e2e_tests()
            else:
                print("⏩ 快速模式: 跳过性能测试、安全测试和端到端测试")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    
    runner.end_time = time.time()
    
    # Generate and save report
    if not args.no_report:
        report = runner.generate_report(results)
        print(report)
        runner.save_report(report)
    
    # Print summaries
    runner.print_performance_summary(results)
    runner.print_security_summary(results)
    
    # Exit with appropriate code
    failed_tests = sum(1 for r in results.values() 
                      if isinstance(r, dict) and not r.get("success", False))
    
    if failed_tests > 0:
        print(f"\n❌ 测试完成，有 {failed_tests} 个测试套件失败")
        sys.exit(1)
    else:
        print("\n✅ 所有测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()