from app.models import Category

def test_create_item(client, db_session):                                                              
    # ① 前体データのカテゴリを作成してコミット                                                         
    category = Category(name="家電製品")                                                                   
    db_session.add(category)                                                                           
    db_session.commit()                                                                                
    db_session.refresh(category)                                                                       
                                                                                                        
    # ② API リクエストの送信                                                                           
    response = client.post(                                                                            
        "/items",                                                                                      
        json={                                                                                         
            "name": "ノートPC",                                                                        
            "price": 100000.0,                                                                         
            "category_id": category.id,                                                                
        },                                                                                             
    )  
    
    assert response.status_code == 201                                                                 
    data = response.json()                                                                             
    assert data["name"] == "ノートPC"
    assert data["category_id"] == category.id       