from pymilvus import (
    connections,
    Collection,
    utility
)

# 1. 连接 Milvus 服务
connections.connect(
    alias="default",
    host="127.0.0.1",    # 根据实际改
    port="19535",
    db_name="llama_index"
)

# 2. 获取目标 collection
col_name = "sitesearch_cuhksz_demo_vectors"
collection = Collection(col_name)

# 3. 查看当前索引情况（确认是 FLAT）
print("切换前索引列表：", utility.list_indexes(col_name))
# 可能输出 ['flat'] 或 ['AUTOINDEX'] 等

# 4. 删除已有索引
#    如果索引名不是默认字段名，可传 name 参数；通常 embedding 字段的索引名即为 field_name
index_name = "embedding"
collection.release()
collection.drop_index(index_name=index_name)
print("已删除旧索引，当前索引列表：", utility.list_indexes(col_name))

# 5. 创建 HNSW 索引
#    index_params 中的 M、efConstruction 可根据需要调优
index_params = {
    "index_type": "HNSW",
    "metric_type": "COSINE",               # 或 "IP"/"COSINE"
    "params": {"M": 32, "efConstruction": 256}
}
collection.create_index(
    field_name="embedding",
    index_params=index_params
)
print("已发起 HNSW 索引构建，状态：", utility.index_building_progress(col_name))

# 6. 等待索引构建完成（可选，也可留作后台异步）
utility.wait_for_index_building_complete(col_name, index_name=index_name)
print("索引构建完成 →", utility.list_indexes(col_name))

# 7. 加载 collection（使索引生效，才能查询时走 HNSW）
collection.load()
print("已加载 collection，ready for search")

# —— 到此，原来 FLAT 索引已被替换为 HNSW —— #
