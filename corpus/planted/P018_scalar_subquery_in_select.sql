SELECT e.EmployeeID, e.FullName, (SELECT MAX(h.OrderDate) FROM dbo.SalesOrderHeader h WHERE h.SalesPersonID = e.EmployeeID) AS LastSale FROM dbo.Employee e;
