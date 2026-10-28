SELECT d.OrderID, p.Name FROM dbo.SalesOrderDetail d JOIN dbo.Product p ON d.UnitPrice = p.ListPrice;
