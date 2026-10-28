SELECT c.CustomerID, c.LastName FROM dbo.Customer c WHERE EXISTS (SELECT * FROM dbo.SalesOrderHeader h WHERE h.CustomerID = c.CustomerID);
