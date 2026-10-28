SELECT ProductID, Name FROM dbo.Product WHERE ProductID NOT IN (SELECT ProductID FROM dbo.SalesOrderDetail WHERE Quantity > 5);
