import chromadb

# 1. DB 경로 설정 (로컬에 저장된 경우)
# docker로 띄웠다면 HttpClient 사용: client = chromadb.HttpClient(host='localhost', port=8000)
client = chromadb.PersistentClient(path="./chroma_db") 

# 2. 컬렉션 목록 확인
collections = client.list_collections()
print(f"총 컬렉션 개수: {len(collections)}")
for col in collections:
    print(f"- 컬렉션 이름: {col.name}")

# 3. 특정 컬렉션의 데이터 미리보기 (상위 5개)
if collections:
    collection_name = collections[0].name  # 첫 번째 컬렉션 선택
    collection = client.get_collection(name=collection_name)
    
    # 데이터 개수 확인
    print(f"\n'{collection_name}' 컬렉션 데이터 개수: {collection.count()}")
    
    # 상위 5개 데이터 조회 (documents, metadatas, ids 만 조회)
    data = collection.peek(limit=5)
    
    print("\n--- 데이터 샘플 (5개) ---")
    for i in range(len(data['ids'])):
        print(f"ID: {data['ids'][i]}")
        print(f"Document: {data['documents'][i]}")
        print(f"Metadata: {data['metadatas'][i]}")
        print("-" * 30)