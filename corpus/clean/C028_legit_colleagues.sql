SELECT e.FullName, m.FullName AS Colleague FROM dbo.Employee e JOIN dbo.Employee m ON e.DepartmentID = m.DepartmentID AND e.EmployeeID <> m.EmployeeID;
