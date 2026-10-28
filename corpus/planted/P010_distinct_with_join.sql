SELECT DISTINCT c.CustomerID, c.LastName FROM dbo.Customer c JOIN dbo.SalesOrderHeader h ON h.CustomerID = c.CustomerID;
