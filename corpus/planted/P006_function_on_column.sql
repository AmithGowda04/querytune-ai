SELECT OrderID, CustomerID FROM dbo.SalesOrderHeader WHERE CONVERT(VARCHAR(10), OrderDate, 120) = '2024-03-01';
