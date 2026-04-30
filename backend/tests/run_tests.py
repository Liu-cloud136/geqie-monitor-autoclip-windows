#!/usr/bin/env python3
"""
测试运行脚本
用于运行项目中的所有测试和性能基准测试
"""

import sys
import os
from pathlib import Path
import argparse
import subprocess
import time

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)


def run_pytest_tests(test_dir: str = None, verbose: bool = True):
    """
    使用 pytest 运行单元测试
    
    Args:
        test_dir: 测试目录或文件
        verbose: 是否显示详细输出
    """
    print("\n" + "="*70)
    print("运行 Pytest 单元测试")
    print("="*70)
    
    cmd = [sys.executable, "-m", "pytest"]
    
    if test_dir:
        cmd.append(test_dir)
    else:
        cmd.append("tests/")
    
    if verbose:
        cmd.extend(["-v", "-s", "--tb=short"])
    else:
        cmd.extend(["-q", "--tb=short"])
    
    print(f"执行命令: {' '.join(cmd)}")
    print("-"*70)
    
    start_time = time.perf_counter()
    result = subprocess.run(cmd, cwd=backend_dir)
    elapsed = time.perf_counter() - start_time
    
    print("-"*70)
    if result.returncode == 0:
        print(f"✅ 所有测试通过! 耗时: {elapsed:.2f} 秒")
    else:
        print(f"❌ 部分测试失败! 耗时: {elapsed:.2f} 秒")
    
    return result.returncode == 0


def run_database_performance_benchmark():
    """
    运行数据库性能基准测试
    """
    print("\n" + "="*70)
    print("运行数据库性能基准测试")
    print("="*70)
    
    from tests.test_database_performance import run_performance_benchmarks
    
    try:
        run_performance_benchmarks()
        print("\n✅ 数据库性能基准测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 数据库性能基准测试失败: {e}")
        return False


def run_large_file_benchmark(
    single: float = None,
    multi_count: int = 5,
    multi_size: float = 50,
    srt_duration: int = 3600,
    full_suite: bool = False
):
    """
    运行大文件处理性能基准测试
    """
    print("\n" + "="*70)
    print("运行大文件处理性能基准测试")
    print("="*70)
    
    from tests.test_large_file_processing import LargeFileProcessingTests
    
    tester = LargeFileProcessingTests()
    
    try:
        if full_suite:
            tester.run_benchmark_suite()
        elif single:
            tester.test_single_large_file(single)
        elif multi_count and multi_size:
            tester.test_multiple_files(multi_count, multi_size)
        elif srt_duration:
            tester.test_srt_file_performance(srt_duration)
        else:
            print("请指定测试参数")
            return False
        
        print("\n✅ 大文件处理性能基准测试完成")
        return True
        
    finally:
        tester.cleanup()


def run_batch_import_benchmark():
    """
    运行批量导入基准测试
    """
    print("\n" + "="*70)
    print("运行批量导入基准测试")
    print("="*70)
    
    from tests.test_batch_import_service import run_batch_import_benchmarks
    
    try:
        run_batch_import_benchmarks()
        print("\n✅ 批量导入基准测试完成")
        return True
    except Exception as e:
        print(f"\n❌ 批量导入基准测试失败: {e}")
        return False


def run_all_tests():
    """
    运行所有测试
    """
    print("\n" + "="*70)
    print("运行所有测试")
    print("="*70)
    
    results = []
    
    results.append(run_pytest_tests(verbose=True))
    
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n✅ 所有测试通过!")
    else:
        print(f"\n❌ {total - passed} 个测试失败")
    
    return passed == total


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='测试运行脚本')
    
    parser.add_argument('--unit', action='store_true', help='只运行单元测试')
    parser.add_argument('--db-bench', action='store_true', help='运行数据库性能基准测试')
    parser.add_argument('--file-bench', action='store_true', help='运行大文件处理基准测试')
    parser.add_argument('--batch-bench', action='store_true', help='运行批量导入基准测试')
    parser.add_argument('--all', action='store_true', help='运行所有测试')
    
    parser.add_argument('--single', type=float, default=None, help='大文件测试: 单个文件大小(MB)')
    parser.add_argument('--multi-count', type=int, default=5, help='大文件测试: 多文件数量')
    parser.add_argument('--multi-size', type=float, default=50, help='大文件测试: 每个文件大小(MB)')
    parser.add_argument('--srt-duration', type=int, default=3600, help='字幕测试: 视频时长(秒)')
    parser.add_argument('--full-suite', action='store_true', help='运行完整基准测试套件')
    
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('--test-dir', type=str, default=None, help='指定测试目录或文件')
    
    args = parser.parse_args()
    
    if args.all:
        return run_all_tests()
    
    if args.unit:
        return run_pytest_tests(args.test_dir, args.verbose)
    
    if args.db_bench:
        return run_database_performance_benchmark()
    
    if args.file_bench:
        return run_large_file_benchmark(
            single=args.single,
            multi_count=args.multi_count,
            multi_size=args.multi_size,
            srt_duration=args.srt_duration,
            full_suite=args.full_suite
        )
    
    if args.batch_bench:
        return run_batch_import_benchmark()
    
    print("""
使用示例:
  python tests/run_tests.py --unit           # 运行所有单元测试
  python tests/run_tests.py --unit -v        # 运行所有单元测试（详细输出）
  python tests/run_tests.py --db-bench       # 运行数据库性能基准测试
  python tests/run_tests.py --file-bench --single 100  # 测试100MB文件
  python tests/run_tests.py --file-bench --multi-count 5 --multi-size 50  # 测试5个50MB文件
  python tests/run_tests.py --file-bench --full-suite  # 运行完整的文件测试套件
  python tests/run_tests.py --all            # 运行所有测试
""")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
