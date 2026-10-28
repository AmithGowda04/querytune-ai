SELECT OrderID, Status FROM dbo.SalesOrderHeader WHERE Status = 1 AND (CustomerID = 10 OR CustomerID = 20);
