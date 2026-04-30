"""
文件上传性能优化配置
"""



# 文件上传chunk_size（越大越好，但需要考虑内存和网络稳定性）

UPLOAD_CHUNK_SIZE = 64 * 1024 * 1024  # 64MB chunks - 极致性能

# 可选配置（根据服务器性能调整）
# UPLOAD_CHUNK_SIZE = 32 * 1024 * 1024  # 32MB chunks - 更快但需要更多内存
# UPLOAD_CHUNK_SIZE = 64 * 1024 * 1024  # 64MB chunks - 最快但需要充足内存

# 最大文件大小限制
MAX_FILE_SIZE = 20 * 1024 * 1024 * 1024  # 20GB



# 内存缓冲区大小（用于异步文件操作）

BUFFER_SIZE = 16 * 1024 * 1024  # 16MB buffer

# 性能优化建议：
# 1. 对于服务器内存 >= 16GB，可以使用32MB或64MB的chunk_size
# 2. 对于服务器内存 < 16GB，建议使用16MB的chunk_size
# 3. chunk_size越大，上传速度越快，但会占用更多内存
# 4. 建议chunk_size不超过服务器总内存的1%

# 当前配置适用于大部分服务器（16MB chunk_size）
# 如需更快速度，可以尝试增大到32MB或64MB
