SELECT DISTINCT p.ProductID, p.Name FROM dbo.Product p JOIN dbo.SalesOrderDetail d ON d.ProductID = p.ProductID WHERE d.Quantity > 10;
