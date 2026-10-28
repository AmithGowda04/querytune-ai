SELECT p.ProductID, p.Name, (SELECT COUNT(*) FROM dbo.SalesOrderDetail d WHERE d.ProductID = p.ProductID) AS TimesSold FROM dbo.Product p;
