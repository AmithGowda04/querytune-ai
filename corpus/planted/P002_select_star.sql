SELECT * FROM dbo.SalesOrderHeader h JOIN dbo.Customer c ON c.CustomerID = h.CustomerID WHERE h.OrderDate >= '2024-01-01';
