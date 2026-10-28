SELECT OrderID, TotalDue FROM dbo.SalesOrderHeader WHERE OrderDate >= DATEADD(DAY, -30, GETDATE());
