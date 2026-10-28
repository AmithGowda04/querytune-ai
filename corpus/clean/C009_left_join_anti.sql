SELECT c.CustomerID, c.LastName FROM dbo.Customer c LEFT JOIN dbo.SalesOrderHeader h ON h.CustomerID = c.CustomerID WHERE h.OrderID IS NULL;
