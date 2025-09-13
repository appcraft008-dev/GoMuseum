#!/usr/bin/env python3
"""
GitHub Actions 工作流验证工具
专门检查GitHub Actions特定的语法和最佳实践
"""
import yaml
import re
import os
from pathlib import Path

def validate_github_actions_syntax(workflow_path):
    """验证GitHub Actions工作流语法和最佳实践"""
    print(f"\n🔍 正在验证: {workflow_path}")
    
    issues = []
    warnings = []
    
    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 解析YAML
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            issues.append(f"❌ YAML解析错误: {e}")
            return issues, warnings
        
        # 检查必需的顶级字段
        if 'name' not in data:
            warnings.append("⚠️  缺少工作流名称 (name)")
        
        # GitHub Actions中'on'是保留字，YAML可能将其解析为True
        if 'on' not in data and True not in data:
            issues.append("❌ 缺少触发条件 (on)")
        elif True in data:
            warnings.append("✅ 检测到触发条件配置")
            
        if 'jobs' not in data:
            issues.append("❌ 缺少工作任务 (jobs)")
            
        # 检查secrets使用语法
        secrets_pattern = r'if:\s*\$\{\{\s*secrets\.\w+\s*\}\}'
        if re.search(secrets_pattern, content):
            issues.append("❌ 发现错误的secrets条件语法: 应使用 'secrets.TOKEN != \"\"' 而非 'secrets.TOKEN'")
            
        # 检查正确的secrets语法
        correct_secrets_pattern = r'if:\s*\$\{\{\s*secrets\.\w+\s*!=\s*[\'\"]\'\s*\}\}'
        correct_matches = re.findall(correct_secrets_pattern, content)
        if correct_matches:
            warnings.append(f"✅ 找到 {len(correct_matches)} 个正确的secrets条件检查")
            
        # 检查Actions版本
        action_version_issues = []
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'uses:' in line and '@' in line:
                if '@v1' in line or '@v2' in line:
                    action_version_issues.append(f"行 {i}: 建议使用更新的Action版本 - {line.strip()}")
                    
        if action_version_issues:
            warnings.extend(action_version_issues[:3])  # 只显示前3个
            
        # 检查环境变量使用
        env_usage = re.findall(r'\$\{\{\s*env\.\w+\s*\}\}', content)
        if env_usage:
            warnings.append(f"✅ 找到 {len(env_usage)} 个环境变量使用")
            
        # 检查工作流依赖
        if 'jobs' in data:
            for job_name, job_data in data['jobs'].items():
                if isinstance(job_data, dict) and 'needs' in job_data:
                    needs = job_data['needs']
                    if isinstance(needs, list):
                        warnings.append(f"✅ 任务 '{job_name}' 有依赖: {', '.join(needs)}")
                    else:
                        warnings.append(f"✅ 任务 '{job_name}' 依赖: {needs}")
        
        # 检查Docker相关配置
        if 'docker' in content.lower():
            warnings.append("✅ 检测到Docker集成配置")
            
        # 检查缓存配置
        if 'cache' in content.lower():
            warnings.append("✅ 检测到缓存配置")
            
        return issues, warnings
        
    except Exception as e:
        issues.append(f"❌ 读取文件时发生错误: {e}")
        return issues, warnings

def main():
    """主函数 - 验证所有GitHub Actions工作流"""
    print("🚀 GitHub Actions 工作流验证工具")
    print("=" * 50)
    
    workflows_dir = Path("/Users/hongyang/Projects/GoMuseum/gomuseum_api/.github/workflows")
    
    if not workflows_dir.exists():
        print("❌ .github/workflows 目录不存在")
        return False
        
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    
    if not workflow_files:
        print("❌ 未找到工作流文件")
        return False
        
    print(f"📁 找到 {len(workflow_files)} 个工作流文件")
    
    all_issues = []
    all_warnings = []
    
    for workflow_file in workflow_files:
        issues, warnings = validate_github_actions_syntax(workflow_file)
        all_issues.extend(issues)
        all_warnings.extend(warnings)
        
        print(f"\n📄 {workflow_file.name}:")
        if issues:
            print("  ❌ 问题:")
            for issue in issues:
                print(f"    {issue}")
        if warnings:
            print("  ⚠️  提醒:")
            for warning in warnings[:5]:  # 限制警告数量
                print(f"    {warning}")
        
        if not issues and not warnings:
            print("  ✅ 语法检查通过")
            
    # 总结报告
    print("\n" + "=" * 50)
    print("📊 验证总结:")
    print(f"  📁 验证文件数: {len(workflow_files)}")
    print(f"  ❌ 发现问题: {len(all_issues)}")
    print(f"  ⚠️  警告提醒: {len(all_warnings)}")
    
    if all_issues:
        print("\n🔥 需要修复的关键问题:")
        for issue in set(all_issues):  # 去重
            print(f"  {issue}")
    
    if not all_issues:
        print("\n🎉 所有工作流语法验证通过！")
        return True
    else:
        print(f"\n⚠️  发现 {len(all_issues)} 个需要修复的问题")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ CI/CD 工作流验证完成 - 状态良好")
        exit(0)
    else:
        print("\n❌ CI/CD 工作流验证完成 - 需要修复问题")
        exit(1)