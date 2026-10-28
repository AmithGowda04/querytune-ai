SELECT c.CustomerID, c.LastName, (SELECT SUM(h.TotalDue) FROM dbo.SalesOrderHeader h WHERE h.CustomerID = c.CustomerID) AS TotalSpent FROM dbo.Customer c;
