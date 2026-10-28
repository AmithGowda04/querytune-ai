SELECT OrderID, Status FROM dbo.SalesOrderHeader WHERE Status NOT IN (1, 2);
