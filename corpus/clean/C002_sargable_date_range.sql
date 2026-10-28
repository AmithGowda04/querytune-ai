SELECT h.OrderID, h.OrderDate, c.LastName FROM dbo.SalesOrderHeader h JOIN dbo.Customer c ON c.CustomerID = h.CustomerID WHERE h.OrderDate >= '2024-01-01' AND h.OrderDate < '2025-01-01';
