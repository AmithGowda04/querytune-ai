SELECT CustomerID, LastName FROM dbo.Customer WHERE CustomerID NOT IN (SELECT CustomerID FROM dbo.SalesOrderHeader);
